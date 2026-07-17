import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.ecommerce.schemas import EcommerceDataset


IntentName = Literal[
    "business_diagnosis", "product_analysis", "competitive_analysis",
    "content_generation", "marketing_strategy", "marketing_campaign_create",
    "ad_optimization", "customer_operations", "price_update",
    "product_publish", "product_unpublish", "automation_rule",
    "autonomous_goal",
]


class IntentPlan(BaseModel):
    intent: IntentName
    mode: Literal["analysis", "content", "mutation", "automation", "autonomous"]
    product_id: str | None = None
    slots: dict[str, Any] = Field(default_factory=dict)
    missing_slots: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.9, ge=0, le=1)
    reasoning: str = "deterministic business rules"


class OperationsIntentPlanner:
    def __init__(self, dataset: EcommerceDataset):
        self.dataset = dataset

    def plan_with_rules(self, message: str) -> IntentPlan:
        text = message.strip()
        product_id = self._match_product(text)
        channel = next((item for item in ("小红书", "抖音", "淘宝", "京东", "Amazon", "微信") if item.lower() in text.lower()), None)
        days_match = re.search(r"(?:最近|近)?\s*(\d+)\s*天", text)
        days = int(days_match.group(1)) if days_match else 30
        slots: dict[str, Any] = {"days": days}
        if channel:
            slots["channel"] = channel

        if any(word in text for word in ("竞品", "竞对", "竞争对手", "市场对比")):
            return self._finish("competitive_analysis", "analysis", product_id, slots, require_product=True)
        if any(word in text for word in ("文案", "标题", "卖点", "种草", "帖子", "广告语")):
            return self._finish("content_generation", "content", product_id, slots, require_product=True, required=("channel",))
        if "下架" in text:
            return self._finish("product_unpublish", "mutation", product_id, slots, require_product=True)
        if "上架" in text:
            return self._finish("product_publish", "mutation", product_id, slots, require_product=True)
        if any(word in text for word in ("调价", "调整价格", "价格调整", "改价", "降价", "涨价")):
            match = re.search(r"(?:调整到|调到|改为|降到|涨到|至)\s*[¥￥]?\s*(\d+(?:\.\d+)?)", text)
            if match:
                slots["new_price"] = float(match.group(1))
            return self._finish("price_update", "mutation", product_id, slots, require_product=True, required=("new_price",))
        if any(word in text for word in ("自动", "定时", "每天", "每周", "监控规则")):
            slots["task_prompt"] = text
            if "每天" in text:
                slots["schedule"] = "daily"
                slots["interval_minutes"] = 1440
            elif "每周" in text:
                slots["schedule"] = "weekly"
                slots["interval_minutes"] = 10080
            return self._finish("automation_rule", "automation", product_id, slots, required=("schedule",))
        if ("创建" in text or "新建" in text or "启动" in text) and any(word in text for word in ("活动", "营销", "推广")):
            budget = re.search(r"(?:日预算|每天预算|预算)\s*[¥￥]?\s*(\d+(?:\.\d+)?)", text)
            if budget:
                slots["daily_budget"] = float(budget.group(1))
            slots["objective"] = "新品冷启动" if "新品" in text or "冷启动" in text else "增长"
            return self._finish("marketing_campaign_create", "mutation", product_id, slots, require_product=True, required=("daily_budget",))
        if any(word in text.upper() for word in ("ACOS", "ROI")) or any(word in text for word in ("广告优化", "投放优化", "关键词优化")):
            return self._finish("ad_optimization", "analysis", product_id, slots)
        if any(word in text for word in ("客户", "用户", "复购", "召回", "人群", "会员")):
            return self._finish("customer_operations", "analysis", product_id, slots)
        if any(word in text for word in ("营销方案", "营销计划", "推广方案", "增长策略")):
            return self._finish("marketing_strategy", "analysis", product_id, slots, require_product=True)
        if any(word in text.upper() for word in ("GMV", "CVR")) or any(word in text for word in ("经营诊断", "为什么下降", "经营情况", "大盘")):
            return self._finish("business_diagnosis", "analysis", product_id, slots)
        if any(word in text for word in ("商品分析", "转化", "库存", "毛利", "表现")):
            return self._finish("product_analysis", "analysis", product_id, slots, require_product=True)
        return IntentPlan(intent="business_diagnosis", mode="analysis", product_id=product_id, slots=slots, missing_slots=["objective"], questions=["你希望我重点解决哪类问题：经营诊断、商品分析、竞品、内容、广告、客户运营，还是执行业务变更？"], confidence=0.35)

    def _finish(self, intent: IntentName, mode: str, product_id: str | None, slots: dict[str, Any], *, require_product: bool = False, required: tuple[str, ...] = ()) -> IntentPlan:
        missing = []
        questions = []
        if require_product and not product_id:
            missing.append("product_id")
            questions.append("请告诉我要处理的商品名称或商品编号。")
        prompts = {
            "channel": "这份内容准备发布在哪个渠道，例如小红书、抖音、淘宝详情页或朋友圈？",
            "new_price": "你希望把商品价格调整到多少元？",
            "daily_budget": "这个活动的日预算是多少元？",
            "schedule": "自动化任务希望按什么频率运行，例如每天 9 点或每周一？",
        }
        for slot in required:
            if slot not in slots:
                missing.append(slot)
                questions.append(prompts[slot])
        return IntentPlan(intent=intent, mode=mode, product_id=product_id, slots=slots, missing_slots=missing, questions=questions)

    def _match_product(self, text: str) -> str | None:
        normalized = text.lower()
        matches = [item.product_id for item in self.dataset.products if item.product_id.lower() in normalized or item.name.lower() in normalized]
        return matches[0] if len(matches) == 1 else None
