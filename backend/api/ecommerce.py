import time
import json
import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.ecommerce.agent import EcommerceAgent
from backend.config import settings
from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.metrics import build_dashboard
from backend.ecommerce.hybrid_agent import HybridEcommerceAgent
from backend.ecommerce.events import analysis_events
from backend.ecommerce.evaluation import EvaluationCase, evaluate_cases
from backend.ecommerce.persistence.repository import EcommerceRepository, VersionConflict
from backend.ecommerce.observability import percentile
from backend.ecommerce.segmentation import build_product_analysis
from backend.ecommerce.tools import EcommerceTools
from backend.ecommerce.customers import analyze_rfm
from backend.ecommerce.funnel import analyze_funnel
from backend.ecommerce.campaign_effect import analyze_campaign_effect
from backend.ecommerce.competitors import analyze_competitor_prices
from backend.ecommerce.forecast import forecast_gmv
from backend.ecommerce.simulation import SimulationEngine
from backend.ecommerce.runtime.service import EcommerceJobService
from backend.ecommerce.growth_workflow import GrowthWorkflowService
from backend.ecommerce.operations_center import build_operations_center
from backend.ecommerce.action_agent import CommerceActionAgent
from backend.ecommerce.llm import configured_team_planner
from backend.ecommerce.automation import AutomationService, WEBHOOK_PROMPTS
from backend.ecommerce.execution_graph import ExecutionPlanningError, LangGraphExecutionAgent
from backend.schemas.common import ApiResponse

router = APIRouter(prefix="/api/ecommerce", tags=["ecommerce-operations-agent"])
_loader = EcommerceDataLoader()
_repository = EcommerceRepository(settings.ECOMMERCE_DATABASE_URL)
_repository_ready = False
_execution_agent: LangGraphExecutionAgent | None = None


class AgentAnalyzeRequest(BaseModel):
    question: str
    session_id: str = ""


class ApprovalRequest(BaseModel):
    expected_version: int = 1
    comment: str = ""
    idempotency_key: str = ""


class SimulationTransitionRequest(BaseModel):
    expected_version: int


class AgentJobRequest(BaseModel):
    question: str
    session_id: str = ""
    idempotency_key: str = ""


class GrowthWorkflowRequest(BaseModel):
    product_id: str
    platform: str = "Amazon US"
    market_keyword: str = ""


class CommerceActionRequest(BaseModel):
    action_type: str
    product_id: str
    parameters: dict = {}


class MemoryUpdateRequest(BaseModel):
    value: dict


class AutomationToggleRequest(BaseModel):
    enabled: bool


class ExecutionTaskRequest(BaseModel):
    goal: str


class ExecutionApprovalRequest(BaseModel):
    expected_version: int
    comment: str = ""


async def _simulation_result():
    await _ensure_repository()
    baseline = _loader.load_cached()
    baseline_date = max(row.date for row in baseline.orders)
    state = await _repository.get_simulation_state(baseline_date)
    return SimulationEngine.apply(baseline, state.step, state.seed, state.version)


async def _dataset():
    return (await _simulation_result()).dataset


async def _ensure_repository() -> None:
    global _repository_ready
    if not _repository_ready:
        await _repository.initialize()
        _repository_ready = True


async def _execution_runtime() -> LangGraphExecutionAgent:
    global _execution_agent
    await _ensure_repository()
    if _execution_agent is None:
        from backend.ecommerce.mcp_client import EcommerceMCPClient
        client = EcommerceMCPClient(_repository.url, persistent=True)
        await client.start()
        _execution_agent = LangGraphExecutionAgent(_repository, await _dataset(), mcp_client=client)
    return _execution_agent


async def close_execution_runtime() -> None:
    global _execution_agent
    if _execution_agent is not None:
        await _execution_agent.mcp.close()
        _execution_agent = None


def _execution_task_data(item) -> dict:
    return {
        "id": item.id, "goal": item.goal, "status": item.status, "operator": item.operator,
        "state": item.state, "events": item.events, "result": item.result, "error": item.error,
        "version": item.version, "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat(),
    }


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
    dataset = await _dataset()
    summary = build_dashboard(dataset)
    return ApiResponse(data=summary.model_dump())


@router.get("/operations-center", response_model=ApiResponse)
async def operations_center():
    return ApiResponse(data=build_operations_center(await _dataset()))


@router.get("/mcp/status", response_model=ApiResponse)
async def mcp_status():
    runtime = await _execution_runtime()
    try:
        tools = await runtime.mcp.list_tools()
    except Exception as exc:
        return ApiResponse(code=503, msg="MCP Server unavailable", data={"server": "ecommerce-operations", "transport": "stdio", "status": "unavailable", "error": str(exc), "tools": []})
    return ApiResponse(data={"server": "ecommerce-operations", "transport": "stdio", "status": "ready", "tools": tools, "health": runtime.mcp.health()})


@router.post("/execution/tasks", response_model=ApiResponse, status_code=201)
async def create_execution_task(request: ExecutionTaskRequest):
    goal = request.goal.strip()
    if not goal:
        raise HTTPException(status_code=400, detail="执行目标不能为空")
    try:
        item = await (await _execution_runtime()).create_task(goal, "workspace-demo", "demo-user")
    except ExecutionPlanningError as exc:
        raise HTTPException(status_code=400, detail=str(exc).split("\nDuring task")[0]) from exc
    return ApiResponse(data=_execution_task_data(item))


@router.get("/execution/tasks", response_model=ApiResponse)
async def execution_tasks():
    await _ensure_repository()
    return ApiResponse(data=[_execution_task_data(item) for item in await _repository.list_execution_tasks("workspace-demo")])


@router.get("/execution/tasks/{task_id}", response_model=ApiResponse)
async def execution_task_detail(task_id: str):
    await _ensure_repository()
    item = await _repository.get_execution_task(task_id, "workspace-demo")
    if item is None:
        raise HTTPException(status_code=404, detail="执行任务不存在")
    return ApiResponse(data=_execution_task_data(item))


@router.post("/execution/tasks/{task_id}/approve", response_model=ApiResponse)
async def approve_execution_task(task_id: str, request: ExecutionApprovalRequest):
    try:
        item = await (await _execution_runtime()).approve_and_run(task_id, "workspace-demo", "demo-user", request.expected_version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="执行任务不存在") from exc
    except VersionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ExecutionPlanningError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(data=_execution_task_data(item))


@router.post("/execution/tasks/{task_id}/rollback", response_model=ApiResponse)
async def rollback_execution_task(task_id: str, request: ExecutionApprovalRequest):
    try:
        item = await (await _execution_runtime()).rollback(task_id, "workspace-demo", "demo-user", request.expected_version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="执行任务不存在") from exc
    except VersionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ExecutionPlanningError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(data=_execution_task_data(item))


@router.post("/actions/proposals", response_model=ApiResponse)
async def create_action_proposal(request: CommerceActionRequest):
    await _ensure_repository()
    try:
        proposal = CommerceActionAgent(await _dataset()).propose(request.action_type, request.product_id, request.parameters)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="product not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    item = await _repository.create_recommendation(proposal["title"], proposal["action_type"], proposal["risk_level"], proposal["reason"], proposal["expected_impact"], [{"action_payload": proposal["payload"]}])
    return ApiResponse(data={"proposal": proposal, "recommendation": _recommendation_data(item)})


@router.post("/actions/{recommendation_id}/execute", response_model=ApiResponse)
async def execute_commerce_action(recommendation_id: str):
    await _ensure_repository()
    try:
        receipt = await CommerceActionAgent(await _dataset(), _repository).execute(recommendation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="action recommendation not found") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(data=receipt)


@router.get("/team/memories", response_model=ApiResponse)
async def team_memories():
    await _ensure_repository()
    items = await _repository.list_agent_memories("workspace-demo")
    if not items:
        from backend.ecommerce.agent_memory import DEFAULT_AGENT_MEMORIES
        for agent, memories in DEFAULT_AGENT_MEMORIES.items():
            for key, value in memories.items():
                await _repository.upsert_agent_memory("workspace-demo", agent, key, value, "system")
        items = await _repository.list_agent_memories("workspace-demo")
    return ApiResponse(data=[{"agent": item.agent, "key": item.memory_key, "value": item.value, "source": item.source, "updated_at": item.updated_at.isoformat()} for item in items])


@router.put("/team/memories/{agent}/{memory_key}", response_model=ApiResponse)
async def update_team_memory(agent: str, memory_key: str, request: MemoryUpdateRequest):
    from backend.ecommerce.multi_agent import TEAM_ROLES
    if agent not in TEAM_ROLES:
        raise HTTPException(status_code=400, detail="unknown specialist agent")
    await _ensure_repository()
    item = await _repository.upsert_agent_memory("workspace-demo", agent, memory_key, request.value, "user")
    return ApiResponse(data={"agent": item.agent, "key": item.memory_key, "value": item.value, "source": item.source})


def _automation_data(item) -> dict:
    return {"id": item.id, "name": item.name, "trigger_type": item.trigger_type, "interval_minutes": item.interval_minutes, "task_prompt": item.task_prompt, "enabled": item.enabled, "last_run_at": item.last_run_at.isoformat() if item.last_run_at else None, "run_count": item.run_count}


@router.get("/automations", response_model=ApiResponse)
async def automations():
    await _ensure_repository()
    items = await AutomationService(_repository).ensure_defaults("workspace-demo")
    return ApiResponse(data=[_automation_data(item) for item in items])


@router.put("/automations/{rule_id}", response_model=ApiResponse)
async def toggle_automation(rule_id: str, request: AutomationToggleRequest):
    try:
        await _ensure_repository()
        item = await AutomationService(_repository).set_enabled(rule_id, "workspace-demo", request.enabled)
        return ApiResponse(data=_automation_data(item))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="automation rule not found") from exc


@router.post("/automations/{rule_id}/run", response_model=ApiResponse, status_code=202)
async def run_automation(rule_id: str):
    try:
        await _ensure_repository()
        service = AutomationService(_repository, await _dataset(), configured_team_planner())
        job = await service.trigger(rule_id, "workspace-demo")
        asyncio.create_task(service.job_service.run_inline(job.id, "workspace-demo"))
        return ApiResponse(data={"job_id": job.id, "status": job.status})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="automation rule not found") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/automations/webhooks/{event_type}", response_model=ApiResponse, status_code=202)
async def automation_webhook(event_type: str):
    prompt = WEBHOOK_PROMPTS.get(event_type)
    if prompt is None:
        raise HTTPException(status_code=404, detail="unsupported webhook event")
    await _ensure_repository()
    service = EcommerceJobService(_repository, await _dataset(), configured_team_planner())
    job = await service.create_job(prompt, "workspace-demo", "", f"webhook-{event_type}-{time.time_ns()}")
    asyncio.create_task(service.run_inline(job.id, "workspace-demo"))
    return ApiResponse(data={"job_id": job.id, "event_type": event_type, "status": job.status})


@router.get("/products", response_model=ApiResponse)
async def products():
    simulation = await _simulation_result()
    dataset = simulation.dataset
    competitors = {item.product_id: item for item in analyze_competitor_prices(dataset)}
    await _ensure_repository()
    catalog_states = {item.product_id: item for item in await _repository.list_catalog_states()}
    product_records = {item.product_id: item for item in dataset.products}
    data = []
    for item in build_product_analysis(dataset):
        row = item.model_dump()
        state = catalog_states.get(item.product_id)
        effective_price = state.price_override if state and state.price_override is not None else product_records[item.product_id].price
        row.update({"price": effective_price, "base_price": product_records[item.product_id].price, "listing_status": state.listing_status if state else "listed", "catalog_version": state.version if state else 0, "competitor_price": competitors[item.product_id].competitor_price, "price_gap": round(effective_price - competitors[item.product_id].competitor_price, 2), "price_index": round(effective_price / competitors[item.product_id].competitor_price * 100, 2), "deltas": simulation.deltas[item.product_id]})
        data.append(row)
    return ApiResponse(data=data)


@router.get("/analytics/funnel", response_model=ApiResponse)
async def funnel_analysis():
    return ApiResponse(data=analyze_funnel(await _dataset()).model_dump())


@router.get("/analytics/forecast", response_model=ApiResponse)
async def gmv_forecast():
    return ApiResponse(data=forecast_gmv(await _dataset(), horizon=7).model_dump())


@router.get("/customers", response_model=ApiResponse)
async def customer_analysis():
    return ApiResponse(data=analyze_rfm(await _dataset()).model_dump())


@router.get("/campaigns/effect", response_model=ApiResponse)
async def campaign_effect():
    return ApiResponse(data=analyze_campaign_effect(await _dataset()).model_dump())


@router.get("/simulation/state", response_model=ApiResponse)
async def simulation_state():
    result = await _simulation_result()
    data = result.state.model_dump(mode="json")
    data["deltas"] = result.deltas
    return ApiResponse(data=data)


@router.post("/simulation/advance", response_model=ApiResponse)
async def simulation_advance(request: SimulationTransitionRequest):
    await _ensure_repository()
    baseline = _loader.load_cached()
    baseline_date = max(row.date for row in baseline.orders)
    state = await _repository.get_simulation_state(baseline_date)
    events = SimulationEngine.events_for_step(baseline, state.step + 1, state.seed)
    try:
        advanced = await _repository.advance_simulation(events, request.expected_version)
    except VersionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    result = SimulationEngine.apply(baseline, advanced.step, advanced.seed, advanced.version)
    data = result.state.model_dump(mode="json")
    data["deltas"] = result.deltas
    return ApiResponse(data=data)


@router.post("/simulation/reset", response_model=ApiResponse)
async def simulation_reset(request: SimulationTransitionRequest):
    await _ensure_repository()
    baseline = _loader.load_cached()
    baseline_date = max(row.date for row in baseline.orders)
    try:
        reset = await _repository.reset_simulation(baseline_date, request.expected_version)
    except VersionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    result = SimulationEngine.apply(baseline, reset.step, reset.seed, reset.version)
    data = result.state.model_dump(mode="json")
    data["deltas"] = result.deltas
    return ApiResponse(data=data)


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
    started = time.perf_counter()
    analysis = await HybridEcommerceAgent(await _dataset(), use_configured_planner=True).analyze(
        question, session_id=session.id, user_id="demo-user", context=context,
    )
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    analysis.session_id = session.id
    await _repository.append_message(session.id, "assistant", analysis.summary)
    await _repository.create_run(
        run_id=analysis.run_id, session_id=session.id, user_id="demo-user",
        execution_mode=analysis.execution_mode, model=settings.LLM_MODEL if analysis.execution_mode == "llm" else "",
        status="completed", fallback_reason=analysis.fallback_reason, total_latency_ms=latency_ms,
        prompt_tokens=analysis.prompt_tokens, completion_tokens=analysis.completion_tokens,
    )
    for trace in analysis.tool_trace:
        await _repository.add_tool_execution(analysis.run_id, trace.tool_name, trace.input, trace.output_summary, latency_ms=trace.latency_ms)
    for action in analysis.recommendations:
        persisted = await _repository.create_recommendation(
            title=action.title, action_type=action.action_type, risk_level=action.risk_level,
            reason=action.reason, expected_impact=action.expected_impact,
            evidence=[item.model_dump() for item in action.evidence], run_id=analysis.run_id,
        )
        action.id = persisted.id
        action.version = persisted.version
    return ApiResponse(data=analysis.model_dump())


@router.post("/agent/stream")
async def analyze_stream(request: AgentAnalyzeRequest):
    response = await analyze(request)
    return EventSourceResponse(analysis_events(response.data or {}))


@router.post("/agent/jobs", response_model=ApiResponse, status_code=202)
async def create_agent_job(request: AgentJobRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="question is required")
    await _ensure_repository()
    service = EcommerceJobService(_repository, team_planner=configured_team_planner())
    job = await service.create_job(request.question.strip(), "workspace-demo", request.session_id, request.idempotency_key or f"job-{request.question.strip()}")
    if settings.AGENT_EXECUTION_MODE == "celery":
        from backend.tasks.ecommerce_agent_task import run_ecommerce_agent
        run_ecommerce_agent.delay(job.id, "workspace-demo")
    else:
        asyncio.create_task(service.run_inline(job.id, "workspace-demo"))
    return ApiResponse(data={"job_id": job.id, "run_id": job.run_id, "status": job.status, "status_url": f"/api/ecommerce/agent/jobs/{job.id}"})


@router.get("/agent/jobs/{job_id}", response_model=ApiResponse)
async def agent_job_status(job_id: str):
    await _ensure_repository()
    job = await _repository.get_agent_job(job_id, "workspace-demo")
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    events = await _repository.list_agent_events(job.id, after_sequence=0)
    completed = next((item for item in reversed(events) if item.event_type == "completed"), None)
    return ApiResponse(data={"job_id": job.id, "run_id": job.run_id, "status": job.status, "cancelled": job.cancelled, "result": completed.payload if completed else None, "created_at": job.created_at.isoformat(), "updated_at": job.updated_at.isoformat()})


@router.delete("/agent/jobs/{job_id}", response_model=ApiResponse)
async def cancel_agent_job(job_id: str):
    await _ensure_repository()
    job = await EcommerceJobService(_repository).cancel(job_id, "workspace-demo")
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return ApiResponse(data={"job_id": job.id, "status": job.status, "cancelled": job.cancelled})


@router.get("/agent/jobs/{job_id}/events")
async def agent_job_events(job_id: str, last_event_id: int = 0):
    await _ensure_repository()
    job = await _repository.get_agent_job(job_id, "workspace-demo")
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    async def stream():
        events = await _repository.list_agent_events(job_id, after_sequence=last_event_id)
        for item in events:
            yield {"id": str(item.sequence), "event": item.event_type, "data": json.dumps(item.payload, ensure_ascii=False)}
    return EventSourceResponse(stream())


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


def _run_data(item) -> dict:
    return {
        "id": item.id, "session_id": item.session_id, "user_id": item.user_id,
        "execution_mode": item.execution_mode, "model": item.model, "status": item.status,
        "fallback_reason": item.fallback_reason, "total_latency_ms": item.total_latency_ms,
        "prompt_tokens": item.prompt_tokens, "completion_tokens": item.completion_tokens,
        "error": item.error, "created_at": item.created_at.isoformat(),
    }


@router.get("/runs", response_model=ApiResponse)
async def runs(execution_mode: str = "", status: str = ""):
    await _ensure_repository()
    return ApiResponse(data=[_run_data(item) for item in await _repository.list_runs(execution_mode, status)])


@router.get("/runs/summary", response_model=ApiResponse)
async def runs_summary():
    await _ensure_repository()
    items = await _repository.list_runs()
    total = len(items)
    successful = sum(item.status == "completed" for item in items)
    fallback = sum(item.execution_mode == "deterministic_fallback" for item in items)
    latencies = [item.total_latency_ms for item in items]
    return ApiResponse(data={
        "total_runs": total,
        "success_rate": round(successful / total * 100, 2) if total else 0,
        "fallback_rate": round(fallback / total * 100, 2) if total else 0,
        "average_latency_ms": round(sum(latencies) / total, 2) if total else 0,
        "p95_latency_ms": percentile(latencies, 0.95),
        "total_tokens": sum(item.prompt_tokens + item.completion_tokens for item in items),
    })


@router.get("/runs/{run_id}", response_model=ApiResponse)
async def run_detail(run_id: str):
    await _ensure_repository()
    item = await _repository.get_run(run_id)
    if item is None:
        raise HTTPException(status_code=404, detail="run not found")
    data = _run_data(item)
    data["tools"] = [
        {"tool_name": tool.tool_name, "input": tool.input_data, "output_summary": tool.output_summary, "latency_ms": tool.latency_ms, "status": tool.status}
        for tool in await _repository.list_tool_executions(run_id)
    ]
    return ApiResponse(data=data)


@router.get("/agent/evaluations", response_model=ApiResponse)
async def evaluation_runs():
    await _ensure_repository()
    return ApiResponse(data=[{"id": item.id, "mode": item.mode, "metrics": item.metrics, "created_at": item.created_at.isoformat()} for item in await _repository.list_evaluation_runs()])


@router.post("/agent/evaluations/run", response_model=ApiResponse)
async def run_evaluation(online: bool = False):
    await _ensure_repository()
    raw = json.loads(Path("data/ecommerce/evaluation_cases.json").read_text(encoding="utf-8"))
    cases = [EvaluationCase.model_validate(item) for item in raw]
    agent = HybridEcommerceAgent(await _dataset(), use_configured_planner=online)

    async def analyze_case(case: EvaluationCase):
        return (await agent.analyze(case.question)).model_dump()

    report = await evaluate_cases(cases, analyze_case)
    mode = "online" if online and settings.DEEPSEEK_API_KEY else "deterministic"
    persisted = await _repository.create_evaluation_run(mode, report.model_dump())
    data = report.model_dump()
    data.update({"id": persisted.id, "mode": mode, "created_at": persisted.created_at.isoformat()})
    return ApiResponse(data=data)


@router.get("/campaigns/plan", response_model=ApiResponse)
async def campaign_plan(goal: str = "大促增长"):
    dataset = await _dataset()
    normalized_goal = goal.strip() or "大促增长"
    plan, trace = EcommerceTools(dataset).generate_campaign_plan(normalized_goal)
    plan["goal"] = normalized_goal
    plan["tool_trace"] = [trace.model_dump()]
    return ApiResponse(data=plan)


def _workflow_snapshot(item) -> dict | None:
    for evidence in item.evidence:
        if evidence.get("label") == "workflow_snapshot":
            return evidence.get("workflow")
    return None


@router.post("/growth/workflows", response_model=ApiResponse)
async def create_growth_workflow(request: GrowthWorkflowRequest):
    await _ensure_repository()
    try:
        workflow = GrowthWorkflowService(await _dataset()).generate(
            request.product_id, request.platform.strip() or "Amazon US", request.market_keyword
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="product not found") from exc
    recommendation = None
    if workflow["compliance"]["status"] == "passed":
        recommendation = await _repository.create_recommendation(
            title=f"Publish {workflow['product_name']} listing to {workflow['platform']}",
            action_type="listing_publish", risk_level="high",
            reason="Cross-border listing passed automated compliance review and requires human approval.",
            expected_impact="Create a sandbox listing publication receipt.",
            evidence=[{"label": "workflow_snapshot", "value": workflow["product_name"], "rule": "approved_before_publish", "workflow": workflow}],
        )
    return ApiResponse(data={"workflow": workflow, "recommendation": _recommendation_data(recommendation) if recommendation else None})


@router.get("/growth/workflows/{recommendation_id}", response_model=ApiResponse)
async def growth_workflow_detail(recommendation_id: str):
    await _ensure_repository()
    item = await _repository.get_recommendation(recommendation_id)
    workflow = _workflow_snapshot(item) if item else None
    if item is None or workflow is None:
        raise HTTPException(status_code=404, detail="growth workflow not found")
    return ApiResponse(data={"workflow": workflow, "recommendation": _recommendation_data(item)})


@router.post("/growth/workflows/{recommendation_id}/publish", response_model=ApiResponse)
async def publish_growth_workflow(recommendation_id: str):
    await _ensure_repository()
    item = await _repository.get_recommendation(recommendation_id)
    workflow = _workflow_snapshot(item) if item else None
    if item is None or workflow is None:
        raise HTTPException(status_code=404, detail="growth workflow not found")
    try:
        receipt = GrowthWorkflowService(await _dataset()).publish(workflow, item.status, item.id)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApiResponse(data={"workflow": workflow, "recommendation": _recommendation_data(item), "receipt": receipt})


@router.get("/recommendations", response_model=ApiResponse)
async def recommendations(status: str = ""):
    await _ensure_repository()
    items = await _repository.list_recommendations(status=status)
    if not items:
        analysis = EcommerceAgent(await _dataset()).analyze("昨天 GMV 为什么下降？")
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
