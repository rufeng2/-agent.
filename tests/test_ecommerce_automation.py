import pytest

from backend.ecommerce.automation import AutomationService, WEBHOOK_PROMPTS
from backend.ecommerce.persistence.repository import EcommerceRepository


@pytest.mark.asyncio
async def test_default_automation_rules_cover_proactive_operations(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'automation.db'}")
    await repository.initialize()
    service = AutomationService(repository)
    rules = await service.ensure_defaults("shop-a")
    assert {item.name for item in rules} == {"每日广告经营日报", "竞品价格巡检", "库存风险巡检", "差评实时预警"}
    assert len(await service.due_rules("shop-a")) == 4
    await repository.dispose()


@pytest.mark.asyncio
async def test_trigger_creates_agent_job_and_disabled_rule_is_blocked(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'automation.db'}")
    await repository.initialize()
    service = AutomationService(repository)
    rule = (await service.ensure_defaults("shop-a"))[0]
    job = await service.trigger(rule.id, "shop-a")
    assert job.question == rule.task_prompt
    updated = await repository.get_automation_rule(rule.id, "shop-a")
    assert updated.run_count == 1
    await service.set_enabled(rule.id, "shop-a", False)
    with pytest.raises(PermissionError):
        await service.trigger(rule.id, "shop-a")
    await repository.dispose()


def test_supported_webhooks_map_to_agent_goals():
    assert set(WEBHOOK_PROMPTS) == {"order_created", "return_created", "inventory_changed", "negative_review"}
