"""Execution-first ecommerce API."""
import os
from pathlib import Path
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.config import settings
from backend.ecommerce.competitors import analyze_competitor_prices
from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.execution_graph import ExecutionPlanningError, LangGraphExecutionAgent
from backend.ecommerce.forecast import forecast_gmv
from backend.ecommerce.funnel import analyze_funnel
from backend.ecommerce.mcp_client import EcommerceMCPClient
from backend.ecommerce.metrics import build_dashboard
from backend.ecommerce.persistence.repository import EcommerceRepository, VersionConflict
from backend.ecommerce.segmentation import build_product_analysis
from backend.ecommerce.simulation import SimulationEngine
from backend.schemas.common import ApiResponse
from backend.utils.auth import get_current_user


router = APIRouter(prefix="/api/ecommerce", tags=["ecommerce-execution-agent"])
_loader = EcommerceDataLoader()
_repository = EcommerceRepository(settings.ECOMMERCE_DATABASE_URL)
_repository_ready = False
_execution_agent: LangGraphExecutionAgent | None = None
_checkpoint_connection = None


def _identity(user: dict) -> tuple[str, str]:
    return user["workspace_id"], user["username"]


def _require_operator(user: dict) -> None:
    if user.get("role") == "viewer":
        raise HTTPException(status_code=403, detail="只读用户不能执行运营变更")


class ExecutionTaskRequest(BaseModel):
    goal: str


class ExecutionApprovalRequest(BaseModel):
    expected_version: int
    comment: str = ""


class SimulationTransitionRequest(BaseModel):
    expected_version: int


async def _ensure_repository() -> None:
    global _repository_ready
    if not _repository_ready:
        await _repository.initialize()
        _repository_ready = True


async def _simulation_result():
    await _ensure_repository()
    baseline = _loader.load_cached()
    baseline_date = max(row.date for row in baseline.orders)
    state = await _repository.get_simulation_state(baseline_date)
    return SimulationEngine.apply(baseline, state.step, state.seed, state.version)


async def _dataset():
    return (await _simulation_result()).dataset


async def _execution_runtime() -> LangGraphExecutionAgent:
    global _execution_agent, _checkpoint_connection
    await _ensure_repository()
    if _execution_agent is None:
        persistent = "PYTEST_CURRENT_TEST" not in os.environ
        client = EcommerceMCPClient(_repository.url, persistent=persistent)
        if persistent:
            await client.start()
        checkpoint_path = Path("data/langgraph_checkpoints.db")
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        _checkpoint_connection = await aiosqlite.connect(checkpoint_path)
        checkpointer = AsyncSqliteSaver(_checkpoint_connection)
        await checkpointer.setup()
        _execution_agent = LangGraphExecutionAgent(_repository, await _dataset(), mcp_client=client, checkpointer=checkpointer)
    return _execution_agent


async def close_execution_runtime() -> None:
    global _execution_agent, _checkpoint_connection
    if _execution_agent is not None:
        await _execution_agent.mcp.close()
        _execution_agent = None
    if _checkpoint_connection is not None:
        await _checkpoint_connection.close()
        _checkpoint_connection = None


def _task_data(item) -> dict:
    return {
        "id": item.id,
        "goal": item.goal,
        "status": item.status,
        "operator": item.operator,
        "state": item.state,
        "events": item.events,
        "result": item.result,
        "error": item.error,
        "version": item.version,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


@router.get("/dashboard", response_model=ApiResponse)
async def dashboard(_user: dict = Depends(get_current_user)):
    return ApiResponse(data=build_dashboard(await _dataset()).model_dump())


@router.get("/mcp/status", response_model=ApiResponse)
async def mcp_status(_user: dict = Depends(get_current_user)):
    runtime = await _execution_runtime()
    try:
        tools = await runtime.mcp.list_tools()
    except Exception as exc:
        return ApiResponse(code=503, msg="MCP Server unavailable", data={
            "server": "ecommerce-operations", "transport": "stdio",
            "status": "unavailable", "error": str(exc), "tools": [],
        })
    return ApiResponse(data={
        "server": "ecommerce-operations", "transport": "stdio", "status": "ready",
        "tools": tools, "health": runtime.mcp.health(),
    })


@router.post("/execution/tasks", response_model=ApiResponse, status_code=201)
async def create_execution_task(request: ExecutionTaskRequest, user: dict = Depends(get_current_user)):
    goal = request.goal.strip()
    if not goal:
        raise HTTPException(status_code=400, detail="执行目标不能为空")
    _require_operator(user)
    workspace_id, operator = _identity(user)
    try:
        item = await (await _execution_runtime()).create_task(goal, workspace_id, operator)
    except ExecutionPlanningError as exc:
        raise HTTPException(status_code=400, detail=str(exc).split("\nDuring task")[0]) from exc
    return ApiResponse(data=_task_data(item))


@router.get("/execution/tasks", response_model=ApiResponse)
async def execution_tasks(user: dict = Depends(get_current_user)):
    await _ensure_repository()
    workspace_id, _operator = _identity(user)
    items = await _repository.list_execution_tasks(workspace_id)
    return ApiResponse(data=[_task_data(item) for item in items])


@router.get("/execution/tasks/{task_id}", response_model=ApiResponse)
async def execution_task_detail(task_id: str, user: dict = Depends(get_current_user)):
    await _ensure_repository()
    workspace_id, _operator = _identity(user)
    item = await _repository.get_execution_task(task_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="执行任务不存在")
    return ApiResponse(data=_task_data(item))


@router.post("/execution/tasks/{task_id}/approve", response_model=ApiResponse)
async def approve_execution_task(task_id: str, request: ExecutionApprovalRequest, user: dict = Depends(get_current_user)):
    _require_operator(user)
    workspace_id, operator = _identity(user)
    try:
        item = await (await _execution_runtime()).approve_and_run(
            task_id, workspace_id, operator, request.expected_version,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="执行任务不存在") from exc
    except VersionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ExecutionPlanningError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(data=_task_data(item))


@router.post("/execution/tasks/{task_id}/rollback", response_model=ApiResponse)
async def rollback_execution_task(task_id: str, request: ExecutionApprovalRequest, user: dict = Depends(get_current_user)):
    _require_operator(user)
    workspace_id, operator = _identity(user)
    try:
        item = await (await _execution_runtime()).rollback(
            task_id, workspace_id, operator, request.expected_version,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="执行任务不存在") from exc
    except VersionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ExecutionPlanningError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(data=_task_data(item))


@router.get("/products", response_model=ApiResponse)
async def products(_user: dict = Depends(get_current_user)):
    simulation = await _simulation_result()
    dataset = simulation.dataset
    competitors = {item.product_id: item for item in analyze_competitor_prices(dataset)}
    catalog_states = {item.product_id: item for item in await _repository.list_catalog_states()}
    product_records = {item.product_id: item for item in dataset.products}
    data = []
    for item in build_product_analysis(dataset):
        row = item.model_dump()
        state = catalog_states.get(item.product_id)
        effective_price = state.price_override if state and state.price_override is not None else product_records[item.product_id].price
        competitor_price = competitors[item.product_id].competitor_price
        row.update({
            "price": effective_price,
            "base_price": product_records[item.product_id].price,
            "listing_status": state.listing_status if state else "listed",
            "catalog_version": state.version if state else 0,
            "competitor_price": competitor_price,
            "price_gap": round(effective_price - competitor_price, 2),
            "price_index": round(effective_price / competitor_price * 100, 2),
            "deltas": simulation.deltas[item.product_id],
        })
        data.append(row)
    return ApiResponse(data=data)


@router.get("/analytics/funnel", response_model=ApiResponse)
async def funnel_analysis(_user: dict = Depends(get_current_user)):
    return ApiResponse(data=analyze_funnel(await _dataset()).model_dump())


@router.get("/analytics/forecast", response_model=ApiResponse)
async def gmv_forecast(_user: dict = Depends(get_current_user)):
    return ApiResponse(data=forecast_gmv(await _dataset(), horizon=7).model_dump())


@router.get("/simulation/state", response_model=ApiResponse)
async def simulation_state(_user: dict = Depends(get_current_user)):
    result = await _simulation_result()
    data = result.state.model_dump(mode="json")
    data["deltas"] = result.deltas
    return ApiResponse(data=data)


@router.post("/simulation/advance", response_model=ApiResponse)
async def simulation_advance(request: SimulationTransitionRequest, user: dict = Depends(get_current_user)):
    _require_operator(user)
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
async def simulation_reset(request: SimulationTransitionRequest, user: dict = Depends(get_current_user)):
    _require_operator(user)
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
