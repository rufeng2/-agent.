from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.ecommerce.agent import EcommerceAgent
from backend.config import settings
from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.metrics import build_dashboard
from backend.ecommerce.hybrid_agent import HybridEcommerceAgent
from backend.ecommerce.events import analysis_events
from backend.ecommerce.persistence.repository import EcommerceRepository, VersionConflict
from backend.ecommerce.segmentation import build_product_analysis
from backend.ecommerce.tools import EcommerceTools
from backend.schemas.common import ApiResponse

router = APIRouter(prefix="/api/ecommerce", tags=["ecommerce-operations-agent"])
_loader = EcommerceDataLoader()
_repository = EcommerceRepository(settings.ECOMMERCE_DATABASE_URL)
_repository_ready = False


class AgentAnalyzeRequest(BaseModel):
    question: str
    session_id: str = ""


class ApprovalRequest(BaseModel):
    expected_version: int = 1
    comment: str = ""
    idempotency_key: str = ""


def _dataset():
    return _loader.load_cached()


async def _ensure_repository() -> None:
    global _repository_ready
    if not _repository_ready:
        await _repository.initialize()
        _repository_ready = True


def _session_data(item, include_messages: bool = False) -> dict:
    data = {"id": item.id, "user_id": item.user_id, "title": item.title, "summary": item.summary, "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat()}
    if include_messages:
        data["messages"] = [{"id": message.id, "role": message.role, "content": message.content, "created_at": message.created_at.isoformat()} for message in item.messages]
    return data


def _recommendation_data(item) -> dict:
    return {
        "id": item.id, "title": item.title, "action_type": item.action_type,
        "risk_level": item.risk_level, "reason": item.reason,
        "expected_impact": item.expected_impact, "evidence": item.evidence,
        "status": item.status, "version": item.version, "operator": item.operator,
        "updated_at": item.updated_at.isoformat(),
    }


@router.get("/dashboard", response_model=ApiResponse)
async def dashboard():
    dataset = _dataset()
    summary = build_dashboard(dataset)
    return ApiResponse(data=summary.model_dump())


@router.get("/products", response_model=ApiResponse)
async def products():
    dataset = _dataset()
    return ApiResponse(data=[item.model_dump() for item in build_product_analysis(dataset)])


@router.post("/agent/analyze", response_model=ApiResponse)
async def analyze(request: AgentAnalyzeRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    await _ensure_repository()
    session = await _repository.get_session(request.session_id) if request.session_id else None
    if session is None:
        session = await _repository.create_session(user_id="demo-user", title=question[:40])
        context = []
    else:
        context = [{"role": item.role, "content": item.content} for item in session.messages]
    await _repository.append_message(session.id, "user", question)
    analysis = await HybridEcommerceAgent(_dataset(), use_configured_planner=True).analyze(
        question, session_id=session.id, user_id="demo-user", context=context,
    )
    analysis.session_id = session.id
    await _repository.append_message(session.id, "assistant", analysis.summary)
    for action in analysis.recommendations:
        persisted = await _repository.create_recommendation(
            title=action.title, action_type=action.action_type, risk_level=action.risk_level,
            reason=action.reason, expected_impact=action.expected_impact,
            evidence=[item.model_dump() for item in action.evidence], run_id=None,
        )
        action.id = persisted.id
        action.version = persisted.version
    return ApiResponse(data=analysis.model_dump())


@router.post("/agent/stream")
async def analyze_stream(request: AgentAnalyzeRequest):
    response = await analyze(request)
    return EventSourceResponse(analysis_events(response.data or {}))


@router.get("/sessions", response_model=ApiResponse)
async def sessions():
    await _ensure_repository()
    return ApiResponse(data=[_session_data(item) for item in await _repository.list_sessions("demo-user")])


@router.get("/sessions/{session_id}", response_model=ApiResponse)
async def session_detail(session_id: str):
    await _ensure_repository()
    item = await _repository.get_session(session_id)
    if item is None:
        raise HTTPException(status_code=404, detail="session not found")
    return ApiResponse(data=_session_data(item, include_messages=True))


@router.get("/campaigns/plan", response_model=ApiResponse)
async def campaign_plan(goal: str = "大促增长"):
    dataset = _dataset()
    normalized_goal = goal.strip() or "大促增长"
    plan, trace = EcommerceTools(dataset).generate_campaign_plan(normalized_goal)
    plan["goal"] = normalized_goal
    plan["tool_trace"] = [trace.model_dump()]
    return ApiResponse(data=plan)


@router.get("/recommendations", response_model=ApiResponse)
async def recommendations(status: str = ""):
    await _ensure_repository()
    items = await _repository.list_recommendations(status=status)
    if not items:
        analysis = EcommerceAgent(_dataset()).analyze("昨天 GMV 为什么下降？")
        for action in analysis.recommendations:
            await _repository.create_recommendation(action.title, action.action_type, action.risk_level, action.reason, action.expected_impact, [item.model_dump() for item in action.evidence])
        items = await _repository.list_recommendations(status=status)
    return ApiResponse(data=[_recommendation_data(item) for item in items])


@router.get("/recommendations/{recommendation_id}", response_model=ApiResponse)
async def recommendation_detail(recommendation_id: str):
    await _ensure_repository()
    item = await _repository.get_recommendation(recommendation_id)
    if item is None:
        raise HTTPException(status_code=404, detail="recommendation not found")
    data = _recommendation_data(item)
    data["approvals"] = [
        {"from_status": record.from_status, "to_status": record.to_status, "operator": record.operator, "comment": record.comment, "created_at": record.created_at.isoformat()}
        for record in await _repository.list_approvals(recommendation_id)
    ]
    return ApiResponse(data=data)


@router.post("/recommendations/{recommendation_id}/approve", response_model=ApiResponse)
async def approve_recommendation(recommendation_id: str, request: ApprovalRequest = ApprovalRequest()):
    try:
        await _ensure_repository()
        key = request.idempotency_key or f"approve-{recommendation_id}-{request.expected_version}"
        item = await _repository.transition_recommendation(recommendation_id, "approved", request.expected_version, "demo-user", request.comment, key)
        return ApiResponse(data=_recommendation_data(item))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="recommendation not found") from exc
    except VersionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/recommendations/{recommendation_id}/reject", response_model=ApiResponse)
async def reject_recommendation(recommendation_id: str, request: ApprovalRequest = ApprovalRequest()):
    try:
        await _ensure_repository()
        key = request.idempotency_key or f"reject-{recommendation_id}-{request.expected_version}"
        item = await _repository.transition_recommendation(recommendation_id, "rejected", request.expected_version, "demo-user", request.comment, key)
        return ApiResponse(data=_recommendation_data(item))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="recommendation not found") from exc
    except VersionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
