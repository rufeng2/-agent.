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
