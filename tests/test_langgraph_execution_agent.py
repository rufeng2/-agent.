import pytest
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.execution_graph import ExecutionPlanningError, LangGraphExecutionAgent
from backend.ecommerce.persistence.repository import EcommerceRepository
from backend.ecommerce.supervisor import ExecutionPlan


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
    stored = await repository.get_campaign(completed.result["campaign"]["campaign_id"], "workspace-1")
    assert stored is not None
    assert stored.status == "active"
    assert completed.events[-1]["agent"] == "Tool Executor"
    await repository.dispose()


@pytest.mark.asyncio
async def test_copy_request_routes_to_content_agent_and_delivers_copy(tmp_path, monkeypatch):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    agent = LangGraphExecutionAgent(repository, EcommerceDataLoader().load_cached())

    async def fake_generate_copy(_goal, product):
        return {
            "headline": "随身鲜榨，轻装出发",
            "body": f"{product['name']}让通勤与健身后的补给更简单。",
            "selling_points": ["轻巧便携", "即榨即饮", "容易清洗"],
            "cta": "立即入手",
            "channel": "小红书",
            "hashtags": ["#便携榨汁杯", "#健康生活"],
            "generation_mode": "llm",
        }

    monkeypatch.setattr(agent.supervisor, "generate_copy", fake_generate_copy)
    task = await agent.create_task("给便携榨汁杯做一个小红书推广文案", "workspace-1", "operator")
    completed = await agent.approve_and_run(task.id, "workspace-1", "operator", task.version)

    assert task.state["action_type"] == "content_generation"
    assert task.state["specialist"] == "content_agent"
    assert completed.result["copy"]["headline"] == "随身鲜榨，轻装出发"
    assert completed.result["copy"]["generation_mode"] == "llm"
    assert "campaign" not in completed.result
    await repository.dispose()


@pytest.mark.asyncio
async def test_competitor_analysis_is_read_only_and_does_not_create_campaign(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    agent = LangGraphExecutionAgent(repository, EcommerceDataLoader().load_cached())

    task = await agent.create_task("给便携榨汁杯做一个小红书竞品分析", "workspace-1", "operator")

    assert task.status == "completed"
    assert task.state["action_type"] == "competitive_analysis"
    assert task.state["specialist"] == "competitor_agent"
    assert task.result["analysis"]["price_comparison"]["competitor_price"] > 0
    assert task.result["analysis"]["opportunities"]
    assert "campaign" not in task.result
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
    assert completed.events[-1]["type"] == "mcp_tool_completed"
    assert completed.result["mcp"] == {"server": "ecommerce-operations", "transport": "stdio", "tool": "set_product_listing"}
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


@pytest.mark.asyncio
async def test_structured_supervisor_plan_routes_specialist(tmp_path, monkeypatch):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    agent = LangGraphExecutionAgent(repository, EcommerceDataLoader().load_cached())

    async def fake_plan(_goal, _context):
        return ExecutionPlan(action_type="product_unpublish", product_id="P003", parameters={}, confidence=0.98, reasoning="inventory risk")

    monkeypatch.setattr(agent.supervisor, "plan", fake_plan)
    task = await agent.create_task("处理库存风险商品", "workspace-1", "operator")

    assert task.state["action_type"] == "product_unpublish"
    assert task.state["specialist"] == "listing_agent"
    assert task.events[0]["detail"].startswith("llm")
    await repository.dispose()


@pytest.mark.asyncio
async def test_native_checkpoint_restores_pending_interrupt(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    dataset = EcommerceDataLoader().load_cached()
    checkpoint_path = tmp_path / "checkpoints.db"

    connection1 = await aiosqlite.connect(checkpoint_path)
    saver1 = AsyncSqliteSaver(connection1)
    await saver1.setup()
    first = LangGraphExecutionAgent(repository, dataset, checkpointer=saver1)
    task = await first.create_task("下架商品 P003", "workspace-1", "operator")
    snapshot1 = await first.graph.aget_state({"configurable": {"thread_id": task.id}})
    assert snapshot1.next == ("approval_gate",)
    await connection1.close()

    connection2 = await aiosqlite.connect(checkpoint_path)
    saver2 = AsyncSqliteSaver(connection2)
    second = LangGraphExecutionAgent(repository, dataset, checkpointer=saver2)
    snapshot2 = await second.graph.aget_state({"configurable": {"thread_id": task.id}})
    assert snapshot2.next == ("approval_gate",)
    completed = await second.approve_and_run(task.id, "workspace-1", "operator", task.version)
    assert completed.status == "completed"
    await connection2.close()
    await repository.dispose()


@pytest.mark.asyncio
async def test_composite_task_executes_price_then_campaign_dag(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    agent = LangGraphExecutionAgent(repository, EcommerceDataLoader().load_cached())

    task = await agent.create_task("把轻量跑步鞋价格调整到269元并创建新品推广活动", "workspace-1", "operator")
    assert [step["id"] for step in task.state["steps"]] == ["price", "campaign"]
    completed = await agent.approve_and_run(task.id, "workspace-1", "operator", task.version)

    assert completed.result["action_type"] == "composite"
    assert [step["status"] for step in completed.result["steps"]] == ["completed", "completed"]
    assert completed.result["campaign"]["status"] == "active"
    await repository.dispose()
