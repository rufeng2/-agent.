import pytest

from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.execution_graph import ExecutionPlanningError, LangGraphExecutionAgent
from backend.ecommerce.persistence.repository import EcommerceRepository


@pytest.mark.asyncio
async def test_langgraph_price_task_interrupts_for_approval_then_executes(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    agent = LangGraphExecutionAgent(repository, EcommerceDataLoader().load_cached())

    task = await agent.create_task("把轻量跑步鞋价格调整到269元", "workspace-1", "operator")
    assert task.status == "waiting_approval"
    assert task.state["specialist"] == "pricing_agent"
    assert [event["agent"] for event in task.events] == ["Supervisor", "Catalog Agent", "Pricing Agent", "Risk Agent"]

    completed = await agent.approve_and_run(task.id, "workspace-1", "operator", task.version)
    states = {item.product_id: item for item in await repository.list_catalog_states()}
    assert completed.status == "completed"
    assert completed.result["before"]["price"] != completed.result["after"]["price"]
    assert states["P002"].price_override == 269
    await repository.dispose()


@pytest.mark.asyncio
async def test_langgraph_routes_marketing_task_to_marketing_agent(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    agent = LangGraphExecutionAgent(repository, EcommerceDataLoader().load_cached())

    task = await agent.create_task("给轻量跑步鞋创建新品冷启动推广活动", "workspace-1", "operator")
    completed = await agent.approve_and_run(task.id, "workspace-1", "operator", task.version)

    assert task.state["specialist"] == "marketing_agent"
    assert completed.result["campaign"]["daily_budget"] > 0
    assert completed.events[-1]["agent"] == "Tool Executor"
    await repository.dispose()


@pytest.mark.asyncio
async def test_task_resumes_from_database_after_runtime_restart(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    dataset = EcommerceDataLoader().load_cached()
    task = await LangGraphExecutionAgent(repository, dataset).create_task("下架商品 P003", "workspace-1", "operator")

    restarted_agent = LangGraphExecutionAgent(repository, dataset)
    completed = await restarted_agent.approve_and_run(task.id, "workspace-1", "operator", task.version)

    assert completed.status == "completed"
    assert completed.result["after"]["listing_status"] == "unlisted"
    assert completed.events[-1]["type"] == "task_completed"
    await repository.dispose()


@pytest.mark.asyncio
async def test_langgraph_rejects_ambiguous_and_unsafe_tasks(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    agent = LangGraphExecutionAgent(repository, EcommerceDataLoader().load_cached())

    with pytest.raises(ExecutionPlanningError, match="商品"):
        await agent.create_task("调整一下价格", "workspace-1", "operator")
    with pytest.raises(ExecutionPlanningError, match="20%"):
        await agent.create_task("把轻量跑步鞋价格调整到100元", "workspace-1", "operator")
    await repository.dispose()
