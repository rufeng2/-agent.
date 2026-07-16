from pathlib import Path

import pytest

from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.multi_agent import MultiAgentCoordinator, SpecialistAgent
from backend.ecommerce.operation_scenarios import detect_operation_scenario
from backend.ecommerce.runtime.graph import EcommerceGraphRuntime


def _dataset():
    return EcommerceDataLoader(Path("data/ecommerce")).load_cached()


def test_supervisor_routes_cross_domain_question_to_multiple_specialists():
    coordinator = MultiAgentCoordinator(_dataset())

    selected = coordinator.route("分析 GMV 下滑、商品库存和客户复购，并制定活动方案")

    assert selected == ["data_analyst", "product", "customer", "campaign"]


def test_product_recommendation_routes_to_product_specialist_only():
    coordinator = MultiAgentCoordinator(_dataset())

    selected = coordinator.route("帮我选一个商品推荐")

    assert selected == ["product"]


@pytest.mark.parametrize(("question", "scenario_id", "agents"), [
    ("大促前补货周期会不会导致断货", "stockout_before_campaign", ["product", "campaign"]),
    ("广告烧钱但没有成交，预算怎么调", "ad_budget_waste", ["data_analyst", "product"]),
    ("高价值老客复购下降怎么召回", "customer_churn", ["customer", "campaign"]),
])
def test_real_operation_pain_points_route_to_specialist_team(question, scenario_id, agents):
    scenario = detect_operation_scenario(question)
    assert scenario and scenario.id == scenario_id
    assert MultiAgentCoordinator(_dataset()).route(question) == agents


def test_specialist_rejects_tool_outside_its_permission_boundary():
    specialist = SpecialistAgent("customer", _dataset())

    with pytest.raises(PermissionError, match="customer.*rank_products"):
        specialist.execute_tool("rank_products", {})


@pytest.mark.asyncio
async def test_graph_returns_supervisor_specialists_risk_and_report_trace():
    runtime = EcommerceGraphRuntime(_dataset(), planner=None)

    result = await runtime.run("分析 GMV 下滑和商品库存风险", context=[])

    trace = result["analysis"]["agent_trace"]
    names = [item["agent"] for item in trace]
    assert names[0] == "supervisor"
    assert "data_analyst" in names
    assert "product" in names
    assert names[-2:] == ["risk_reviewer", "report_writer"]
    assert result["analysis"]["execution_mode"] == "multi_agent_deterministic"


@pytest.mark.asyncio
async def test_product_recommendation_returns_a_product_not_gmv_diagnosis():
    result = await EcommerceGraphRuntime(_dataset(), planner=None).run("帮我选一个商品推荐", context=[])

    assert result["analysis"]["intent"] == "product_recommendation"
    assert result["analysis"]["summary"].startswith("推荐优先考虑")
    assert "GMV 下滑" not in result["analysis"]["summary"]
    assert [item["agent"] for item in result["analysis"]["agent_trace"]] == [
        "supervisor", "product", "risk_reviewer", "report_writer"
    ]


@pytest.mark.asyncio
async def test_result_exposes_business_pain_point_and_decision_target():
    result = await EcommerceGraphRuntime(_dataset(), planner=None).run("广告烧钱但没有成交，预算怎么调", context=[])
    context = result["analysis"]["scenario_context"]
    assert context["scenario"] == "ad_budget_waste"
    assert "预算" in context["pain_point"]
    assert "重新分配预算" in context["decision"]
