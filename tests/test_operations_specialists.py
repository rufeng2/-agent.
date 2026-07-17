import pytest

from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.intent_planner import OperationsIntentPlanner
from backend.ecommerce.specialists import OperationsSpecialistTeam


@pytest.mark.parametrize("message", [
    "分析最近30天GMV为什么下降",
    "看看轻量跑步鞋的转化和库存",
    "给便携榨汁杯做一个小红书竞品分析",
    "优化轻量跑步鞋的广告ACOS",
    "分析高价值客户复购和召回机会",
    "给轻量跑步鞋做营销方案",
])
def test_analysis_specialists_return_evidence_and_actions(message):
    dataset = EcommerceDataLoader().load_cached()
    plan = OperationsIntentPlanner(dataset).plan_with_rules(message)
    report = OperationsSpecialistTeam(dataset).run(plan)

    assert report["summary"]
    assert report["evidence"]
    assert report["actions"]
    assert report["generation_mode"] in {"analytics", "template", "llm"}
