from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.hybrid_agent import HybridEcommerceAgent
from backend.ecommerce.planning import AgentPlan, PlannedTool


class FakePlanner:
    def __init__(self, plan=None, error=None):
        self.plan_result = plan
        self.error = error
        self.prompt_tokens = 12
        self.completion_tokens = 8

    async def plan(self, question, context):
        if self.error:
            raise self.error
        return self.plan_result

    async def summarize(self, question, results):
        return "模型基于工具证据生成的经营结论"


def _dataset():
    return EcommerceDataLoader(Path("data/ecommerce")).load()


def test_plan_rejects_more_than_six_steps():
    with pytest.raises(ValidationError):
        AgentPlan(intent="business_diagnosis", steps=[PlannedTool(tool_name="get_kpi_snapshot") for _ in range(7)])


def test_plan_rejects_unknown_tool():
    with pytest.raises(ValidationError):
        PlannedTool(tool_name="execute_arbitrary_sql")


@pytest.mark.asyncio
async def test_hybrid_agent_executes_valid_structured_plan():
    planner = FakePlanner(AgentPlan(
        intent="business_diagnosis",
        steps=[PlannedTool(tool_name="get_kpi_snapshot"), PlannedTool(tool_name="explain_gmv_attribution")],
    ))
    result = await HybridEcommerceAgent(_dataset(), planner=planner).analyze("昨天 GMV 为什么下降？")

    assert result.execution_mode == "llm"
    assert result.fallback_reason == ""
    assert [step.tool_name for step in result.tool_trace] == ["get_kpi_snapshot", "explain_gmv_attribution"]
    assert result.evidence
    assert result.summary == "模型基于工具证据生成的经营结论"
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 8
    assert all(step.latency_ms >= 0 for step in result.tool_trace)


@pytest.mark.asyncio
async def test_hybrid_agent_falls_back_when_planner_is_unavailable():
    result = await HybridEcommerceAgent(_dataset(), planner=FakePlanner(error=TimeoutError())).analyze("哪些广告 ROI 太低？")

    assert result.execution_mode == "deterministic_fallback"
    assert result.fallback_reason == "llm_timeout"
    assert result.tool_trace
    assert result.recommendations


@pytest.mark.asyncio
async def test_campaign_goal_from_question_reaches_campaign_tool():
    result = await HybridEcommerceAgent(_dataset(), planner=None).analyze("制定新品冷启动活动方案")

    campaign_step = next(step for step in result.tool_trace if step.tool_name == "generate_campaign_plan")
    assert campaign_step.input["goal"] == "新品冷启动"


@pytest.mark.asyncio
async def test_one_failed_tool_keeps_completed_evidence_and_warning():
    planner = FakePlanner(AgentPlan(
        intent="business_diagnosis",
        steps=[PlannedTool(tool_name="forecast_gmv"), PlannedTool(tool_name="get_kpi_snapshot")],
    ))
    agent = HybridEcommerceAgent(_dataset(), planner=planner)
    original = agent.registry.execute

    def execute(name, arguments):
        if name == "forecast_gmv":
            raise RuntimeError("forecast unavailable")
        return original(name, arguments)

    agent.registry.execute = execute
    result = await agent.analyze("诊断经营情况")

    assert result.execution_mode == "llm"
    assert [step.tool_name for step in result.tool_trace] == ["get_kpi_snapshot"]
    assert result.evidence
    assert "forecast_gmv" in result.warnings[0]
