import pytest

from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.intent_planner import OperationsIntentPlanner


@pytest.fixture
def planner():
    return OperationsIntentPlanner(EcommerceDataLoader().load_cached())


@pytest.mark.parametrize(("message", "intent", "mode"), [
    ("给便携榨汁杯做一个小红书竞品分析", "competitive_analysis", "analysis"),
    ("分析最近30天GMV为什么下降", "business_diagnosis", "analysis"),
    ("看看轻量跑步鞋的转化和库存", "product_analysis", "analysis"),
    ("优化轻量跑步鞋的广告ACOS", "ad_optimization", "analysis"),
    ("分析高价值客户复购和召回机会", "customer_operations", "analysis"),
    ("把轻量跑步鞋价格调整到269元", "price_update", "mutation"),
    ("下架商品P003", "product_unpublish", "mutation"),
])
def test_planner_distinguishes_operational_intents(planner, message, intent, mode):
    plan = planner.plan_with_rules(message)
    assert plan.intent == intent
    assert plan.mode == mode


def test_planner_requests_missing_copy_channel(planner):
    plan = planner.plan_with_rules("给便携榨汁杯写推广文案")
    assert plan.intent == "content_generation"
    assert plan.missing_slots == ["channel"]
    assert "渠道" in plan.questions[0]


def test_planner_requests_campaign_budget_instead_of_inventing_it(planner):
    plan = planner.plan_with_rules("给轻量跑步鞋创建新品推广活动")
    assert plan.intent == "marketing_campaign_create"
    assert "daily_budget" in plan.missing_slots
    assert any("预算" in question for question in plan.questions)


def test_planner_does_not_route_competitor_analysis_to_campaign(planner):
    plan = planner.plan_with_rules("给便携榨汁杯做一个小红书竞品分析")
    assert plan.intent == "competitive_analysis"
    assert plan.missing_slots == []
    assert plan.slots["channel"] == "小红书"
