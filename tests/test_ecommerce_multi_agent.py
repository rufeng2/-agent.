from pathlib import Path

import pytest

from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.multi_agent import MultiAgentCoordinator, SpecialistAgent
from backend.ecommerce.runtime.graph import EcommerceGraphRuntime


def _dataset():
    return EcommerceDataLoader(Path("data/ecommerce")).load_cached()


def test_supervisor_routes_cross_domain_question_to_multiple_specialists():
    coordinator = MultiAgentCoordinator(_dataset())

    selected = coordinator.route("分析 GMV 下滑、商品库存和客户复购，并制定活动方案")

    assert selected == ["data_analyst", "product", "customer", "campaign"]


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
