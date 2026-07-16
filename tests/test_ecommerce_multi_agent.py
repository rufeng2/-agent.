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

    assert selected == ["product_research", "pricing", "listing", "advertising", "customer_service"]


def test_product_recommendation_routes_to_product_specialist_only():
    coordinator = MultiAgentCoordinator(_dataset())

    selected = coordinator.route("帮我选一个商品推荐")

    assert selected == ["product_research"]


@pytest.mark.parametrize(("question", "scenario_id", "agents"), [
    ("大促前补货周期会不会导致断货", "stockout_before_campaign", ["product_research", "advertising"]),
    ("广告烧钱但没有成交，预算怎么调", "ad_budget_waste", ["advertising", "pricing"]),
    ("高价值老客复购下降怎么召回", "customer_churn", ["customer_service", "advertising"]),
])
def test_real_operation_pain_points_route_to_specialist_team(question, scenario_id, agents):
    scenario = detect_operation_scenario(question)
    assert scenario and scenario.id == scenario_id
    assert MultiAgentCoordinator(_dataset()).route(question) == agents


def test_specialist_rejects_tool_outside_its_permission_boundary():
    specialist = SpecialistAgent("customer_service", _dataset())

    with pytest.raises(PermissionError, match="customer_service.*rank_products"):
        specialist.execute_tool("rank_products", {})


@pytest.mark.asyncio
async def test_graph_returns_supervisor_specialists_risk_and_report_trace():
    runtime = EcommerceGraphRuntime(_dataset(), planner=None)

    result = await runtime.run("分析 GMV 下滑和商品库存风险", context=[])

    trace = result["analysis"]["agent_trace"]
    names = [item["agent"] for item in trace]
    assert names[0] == "supervisor"
    assert "product_research" in names
    assert "pricing" in names
    assert names[-1] == "supervisor_summary"
    assert result["analysis"]["execution_mode"] == "openclaw_team_deterministic"


@pytest.mark.asyncio
async def test_product_recommendation_returns_a_product_not_gmv_diagnosis():
    result = await EcommerceGraphRuntime(_dataset(), planner=None).run("帮我选一个商品推荐", context=[])

    assert result["analysis"]["intent"] == "product_recommendation"
    assert result["analysis"]["summary"].startswith("推荐优先考虑")
    assert "GMV 下滑" not in result["analysis"]["summary"]
    assert [item["agent"] for item in result["analysis"]["agent_trace"]] == [
        "supervisor", "product_research", "supervisor_summary"
    ]


@pytest.mark.asyncio
async def test_result_exposes_business_pain_point_and_decision_target():
    result = await EcommerceGraphRuntime(_dataset(), planner=None).run("广告烧钱但没有成交，预算怎么调", context=[])
    context = result["analysis"]["scenario_context"]
    assert context["scenario"] == "ad_budget_waste"
    assert "预算" in context["pain_point"]
    assert "重新分配预算" in context["decision"]


@pytest.mark.asyncio
async def test_new_product_launch_returns_five_specialist_deliverables():
    result = await EcommerceGraphRuntime(_dataset(), planner=None).run(
        "我要把一款新品从 0 做到 Amazon US 上架，请团队给出完整方案", context=[]
    )
    analysis = result["analysis"]
    assert [item["agent"] for item in analysis["agent_trace"]] == [
        "supervisor", "product_research", "pricing", "listing",
        "advertising", "customer_service", "supervisor_summary",
    ]
    assert set(analysis["team_deliverables"]) == {
        "product_research", "pricing", "listing", "advertising", "customer_service",
    }
    assert analysis["team_deliverables"]["listing"]["title"]
    assert analysis["team_deliverables"]["pricing"]["recommended_price"] > 0
