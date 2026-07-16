from pathlib import Path

import pytest

from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.runtime.graph import EcommerceGraphRuntime


def _dataset():
    return EcommerceDataLoader(Path("data/ecommerce")).load_cached()


@pytest.mark.asyncio
async def test_langgraph_runs_context_analysis_and_completion_nodes():
    runtime = EcommerceGraphRuntime(_dataset(), planner=None)
    result = await runtime.run("昨天 GMV 为什么下降？", context=[])

    assert result["status"] == "completed"
    assert result["node_trace"] == [
        "load_context", "supervisor", "product_research", "pricing", "listing",
        "advertising", "customer_service", "supervisor_summary", "complete",
    ]
    assert result["analysis"]["execution_mode"] == "openclaw_team_deterministic"
    assert result["analysis"]["tool_trace"]


@pytest.mark.asyncio
async def test_langgraph_cancellation_stops_before_agent_execution():
    runtime = EcommerceGraphRuntime(_dataset(), planner=None, is_cancelled=lambda: True)
    result = await runtime.run("分析经营情况", context=[])

    assert result["status"] == "cancelled"
    assert result["node_trace"] == ["load_context", "cancelled"]
    assert result.get("analysis") is None


class FakeTeamPlanner:
    prompt_tokens = 21
    completion_tokens = 9

    async def route_team(self, question, context):
        return ["product_research", "pricing"]

    async def summarize_team(self, question, deliverables):
        return "模型主管已汇总选品和定价方案。"


@pytest.mark.asyncio
async def test_online_team_planner_routes_and_summarizes_specialists():
    result = await EcommerceGraphRuntime(_dataset(), planner=FakeTeamPlanner()).run("帮我选品并定价", context=[])

    assert [item["agent"] for item in result["analysis"]["agent_trace"]] == [
        "supervisor", "product_research", "pricing", "supervisor_summary",
    ]
    assert result["analysis"]["summary"] == "模型主管已汇总选品和定价方案。"
    assert result["analysis"]["execution_mode"] == "openclaw_team_llm"
    assert result["analysis"]["prompt_tokens"] == 21


class InvalidTeamPlanner(FakeTeamPlanner):
    async def route_team(self, question, context):
        return ["shell_agent"]


@pytest.mark.asyncio
async def test_unknown_llm_agent_falls_back_to_deterministic_team():
    result = await EcommerceGraphRuntime(_dataset(), planner=InvalidTeamPlanner()).run("帮我选一个商品推荐", context=[])

    assert [item["agent"] for item in result["analysis"]["agent_trace"]] == [
        "supervisor", "product_research", "supervisor_summary",
    ]
    assert result["analysis"]["execution_mode"] == "openclaw_team_deterministic"
    assert result["analysis"]["fallback_reason"] == "invalid_team_route"
