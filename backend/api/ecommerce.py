from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.ecommerce.agent import EcommerceAgent
from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.metrics import build_dashboard
from backend.ecommerce.recommendations import RecommendationStore
from backend.ecommerce.segmentation import build_product_analysis
from backend.ecommerce.tools import EcommerceTools
from backend.schemas.common import ApiResponse

router = APIRouter(prefix="/api/ecommerce", tags=["ecommerce-operations-agent"])
_store = RecommendationStore()
_loader = EcommerceDataLoader()


class AgentAnalyzeRequest(BaseModel):
    question: str


def _dataset():
    return _loader.load_cached()


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
    dataset = _dataset()
    analysis = EcommerceAgent(dataset).analyze(question)
    _store.seed_from_analysis(analysis)
    return ApiResponse(data=analysis.model_dump())


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
    if not _store.list():
        analysis = EcommerceAgent(_dataset()).analyze("昨天 GMV 为什么下降？")
        _store.seed_from_analysis(analysis)
    return ApiResponse(data=[item.model_dump() for item in _store.list(status=status)])


@router.post("/recommendations/{recommendation_id}/approve", response_model=ApiResponse)
async def approve_recommendation(recommendation_id: str):
    try:
        return ApiResponse(data=_store.approve(recommendation_id, operator="demo-user").model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="recommendation not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/recommendations/{recommendation_id}/reject", response_model=ApiResponse)
async def reject_recommendation(recommendation_id: str):
    try:
        return ApiResponse(data=_store.reject(recommendation_id, operator="demo-user").model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="recommendation not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
