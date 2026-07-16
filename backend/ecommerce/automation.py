from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.ecommerce.runtime.service import EcommerceJobService


DEFAULT_AUTOMATIONS = (
    ("每日广告经营日报", "cron", 1440, "生成昨日广告日报，找出高花费零转化计划、ACOS 异常和预算调整建议"),
    ("竞品价格巡检", "heartbeat", 360, "检查竞品价格和促销变化，判断主推商品是否需要调整价格策略"),
    ("库存风险巡检", "heartbeat", 120, "检查安全库存、补货周期和活动库存，发现断货风险时给出限量与补货建议"),
    ("差评实时预警", "heartbeat", 60, "检查新增低评分评价和高频问题，生成客服处理建议并同步 Listing 优化项"),
)


class AutomationService:
    def __init__(self, repository, dataset=None, team_planner=None):
        self.repository = repository
        self.job_service = EcommerceJobService(repository, dataset, team_planner)

    async def ensure_defaults(self, workspace_id: str):
        rules = await self.repository.list_automation_rules(workspace_id)
        if not rules:
            for name, trigger_type, interval, prompt in DEFAULT_AUTOMATIONS:
                await self.repository.create_automation_rule(workspace_id, name, trigger_type, interval, prompt)
            rules = await self.repository.list_automation_rules(workspace_id)
        return rules

    async def trigger(self, rule_id: str, workspace_id: str):
        rule = await self.repository.get_automation_rule(rule_id, workspace_id)
        if rule is None:
            raise KeyError(rule_id)
        if not rule.enabled:
            raise PermissionError("Automation rule is disabled")
        job = await self.job_service.create_job(rule.task_prompt, workspace_id, "", f"automation-{rule.id}-{uuid4()}")
        await self.repository.update_automation_rule(rule.id, workspace_id, mark_run=True)
        return job

    async def due_rules(self, workspace_id: str):
        now = datetime.now(timezone.utc)
        rules = await self.ensure_defaults(workspace_id)
        return [rule for rule in rules if rule.enabled and (rule.last_run_at is None or rule.last_run_at + timedelta(minutes=rule.interval_minutes) <= now)]

    async def set_enabled(self, rule_id: str, workspace_id: str, enabled: bool):
        rule = await self.repository.update_automation_rule(rule_id, workspace_id, enabled=enabled)
        if rule is None:
            raise KeyError(rule_id)
        return rule


WEBHOOK_PROMPTS = {
    "order_created": "收到新订单事件，检查商品库存和履约风险，并给出需要人工处理的异常项",
    "return_created": "收到退货事件，分析可能的商品、Listing 和客服原因，生成处理与预防方案",
    "inventory_changed": "收到库存变化事件，检查安全库存、补货周期和在途数量，判断是否需要限制投放",
    "negative_review": "收到低评分评价事件，生成客服回复草稿、差评预警和 Listing 修复建议",
}
