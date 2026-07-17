import pytest

from backend.ecommerce.conversation import OperationsConversationService
from backend.ecommerce.data_loader import EcommerceDataLoader
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
