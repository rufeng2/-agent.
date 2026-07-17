import pytest

from backend.ecommerce.conversation import OperationsConversationService
from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.execution_graph import LangGraphExecutionAgent
from backend.ecommerce.persistence.repository import EcommerceRepository


@pytest.mark.asyncio
async def test_ambiguous_request_asks_question_without_execution_task(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    service = OperationsConversationService(repository, EcommerceDataLoader().load_cached())

    reply = await service.send("帮我优化一下", "workspace-1", "alice")

    assert reply.status == "needs_clarification"
    assert reply.questions
    assert await repository.list_execution_tasks("workspace-1") == []
    session = await repository.get_session(reply.session_id)
    assert [message.role for message in session.messages] == ["user", "assistant"]
    await repository.dispose()


@pytest.mark.asyncio
async def test_clarification_answer_resumes_original_request(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    service = OperationsConversationService(repository, EcommerceDataLoader().load_cached())
    first = await service.send("给便携榨汁杯写推广文案", "workspace-1", "alice")

    reply = await service.send("小红书，语气生活化", "workspace-1", "alice", first.session_id)

    assert first.status == "needs_clarification"
    assert reply.status == "completed"
    assert reply.plan.intent == "content_generation"
    assert reply.report["channel"] == "小红书"
    await repository.dispose()


@pytest.mark.asyncio
async def test_competitor_analysis_returns_evidence_without_task_or_campaign(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    service = OperationsConversationService(repository, EcommerceDataLoader().load_cached())

    reply = await service.send("给便携榨汁杯做一个小红书竞品分析", "workspace-1", "alice")

    assert reply.status == "completed"
    assert reply.plan.intent == "competitive_analysis"
    assert reply.report["evidence"]
    assert reply.report["opportunities"]
    assert await repository.list_execution_tasks("workspace-1") == []
    await repository.dispose()


@pytest.mark.asyncio
async def test_automation_request_creates_disabled_rule_draft(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    service = OperationsConversationService(repository, EcommerceDataLoader().load_cached())

    reply = await service.send("每天自动检查库存风险", "workspace-1", "alice")
    rules = await repository.list_automation_rules("workspace-1")

    assert reply.status == "completed"
    assert len(rules) == 1
    assert rules[0].enabled is False
    assert rules[0].interval_minutes == 1440
    await repository.dispose()


@pytest.mark.asyncio
async def test_followup_resolves_previous_report_and_asks_for_action_selection(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    service = OperationsConversationService(repository, EcommerceDataLoader().load_cached())
    first = await service.send("给便携榨汁杯做一个小红书竞品分析", "workspace-1", "alice")

    followup = await service.send("实现你的建议动作", "workspace-1", "alice", first.session_id)

    assert followup.status == "needs_clarification"
    assert "1." in followup.message
    assert "先产出 3 组差异化内容" in followup.message
    assert "经营诊断" not in followup.message
    await repository.dispose()


@pytest.mark.asyncio
async def test_selecting_previous_content_action_reuses_product_and_channel(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    service = OperationsConversationService(repository, EcommerceDataLoader().load_cached())
    first = await service.send("给便携榨汁杯做一个小红书竞品分析", "workspace-1", "alice")
    await service.send("实现你的建议动作", "workspace-1", "alice", first.session_id)

    selected = await service.send("执行第一个", "workspace-1", "alice", first.session_id)

    assert selected.status == "completed"
    assert selected.plan.intent == "content_generation"
    assert selected.plan.product_id == "P003"
    assert selected.report["channel"] == "小红书"
    await repository.dispose()


@pytest.mark.asyncio
async def test_autonomous_goal_clarifies_then_runs_closed_loop(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    service = OperationsConversationService(repository, EcommerceDataLoader().load_cached())
    first = await service.send("自主提升便携榨汁杯转化率", "workspace-1", "alice")

    completed = await service.send("未来7天提升15%，预算1000元", "workspace-1", "alice", first.session_id)

    assert first.status == "needs_clarification"
    assert completed.status == "completed"
    assert completed.plan.intent == "autonomous_goal"
    assert completed.report["autonomous_run"]["status"] == "succeeded"
    assert completed.report["autonomous_run"]["reflections"][0]["decision"] == "replan"
    await repository.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", ["500", "500元", "日预算500"])
async def test_campaign_budget_answer_fills_pending_slot_without_repeating_question(tmp_path, answer):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    service = OperationsConversationService(repository, EcommerceDataLoader().load_cached())
    first = await service.send("给轻量跑步鞋创建新品冷启动推广活动", "workspace-1", "alice")

    reply = await service.send(answer, "workspace-1", "alice", first.session_id)

    assert first.status == "needs_clarification"
    assert reply.status == "waiting_approval"
    assert reply.plan.slots["daily_budget"] == 500
    assert "预算是多少" not in reply.message
    await repository.dispose()


@pytest.mark.asyncio
async def test_campaign_budget_clarification_reaches_execution_task(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    dataset = EcommerceDataLoader().load_cached()
    execution_agent = LangGraphExecutionAgent(repository, dataset)
    service = OperationsConversationService(repository, dataset, execution_agent)
    first = await service.send("给轻量跑步鞋创建新品冷启动推广活动", "workspace-1", "alice")

    reply = await service.send("500元", "workspace-1", "alice", first.session_id)
    task = await repository.get_execution_task(reply.task["id"], "workspace-1")

    assert reply.status == "waiting_approval"
    assert task.state["parameters"]["daily_budget"] == 500
    assert task.state["parameters"]["campaign"]["daily_budget"] == 500
    await repository.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", ["便携榨汁杯", "P003"])
async def test_product_answer_fills_pending_content_product_slot(tmp_path, answer):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    service = OperationsConversationService(repository, EcommerceDataLoader().load_cached())
    first = await service.send("写一篇小红书推广文案", "workspace-1", "alice")

    reply = await service.send(answer, "workspace-1", "alice", first.session_id)

    assert first.plan.missing_slots == ["product_id"]
    assert reply.status == "completed"
    assert reply.plan.product_id == "P003"
    assert "商品名称或商品编号" not in reply.message
    await repository.dispose()


@pytest.mark.asyncio
async def test_complete_first_turn_copy_request_does_not_lazy_load_detached_session(tmp_path, monkeypatch):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    dataset = EcommerceDataLoader().load_cached()
    execution_agent = LangGraphExecutionAgent(repository, dataset)

    async def fake_generate_copy(_goal, product):
        return {
            "headline": f"{product['name']}推广文案",
            "body": "基于已知商品事实生成的正文。",
            "selling_points": ["轻巧便携", "日常使用", "清洁方便"],
            "cta": "查看商品",
            "channel": "小红书",
            "hashtags": ["#便携生活"],
            "generation_mode": "llm",
        }

    monkeypatch.setattr(execution_agent.supervisor, "generate_copy", fake_generate_copy)
    service = OperationsConversationService(repository, dataset, execution_agent)

    reply = await service.send("给便携榨汁杯做一个小红书推广文案", "workspace-1", "alice")

    assert reply.status == "completed"
    assert reply.report["headline"] == "便携榨汁杯推广文案"
    await repository.dispose()


@pytest.mark.asyncio
async def test_price_answer_fills_pending_price_slot(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    service = OperationsConversationService(repository, EcommerceDataLoader().load_cached())
    first = await service.send("调整轻量跑步鞋价格", "workspace-1", "alice")

    reply = await service.send("269元", "workspace-1", "alice", first.session_id)

    assert reply.status == "waiting_approval"
    assert reply.plan.slots["new_price"] == 269
    await repository.dispose()
