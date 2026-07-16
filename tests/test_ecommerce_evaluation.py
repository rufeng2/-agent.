import json
from pathlib import Path

import pytest

from backend.ecommerce.evaluation import EvaluationCase, evaluate_cases
from backend.ecommerce.agent import EcommerceAgent
from backend.ecommerce.data_loader import EcommerceDataLoader


class PerfectAgent:
    async def analyze_case(self, case: EvaluationCase):
        return {
            "intent": case.expected_intent,
            "tool_trace": [{"tool_name": name, "input": {"goal": case.expected_goal} if case.expected_goal else {}} for name in case.expected_tools],
            "evidence": [{"label": "指标", "value": "1"}],
            "risk_level": case.expected_risk,
            "execution_mode": "deterministic_fallback",
        }


def test_evaluation_dataset_has_required_size_and_category_coverage():
    cases = json.loads(Path("data/ecommerce/evaluation_cases.json").read_text(encoding="utf-8"))
    assert len(cases) >= 40
    assert len({item["category"] for item in cases}) >= 8


@pytest.mark.asyncio
async def test_evaluator_scores_each_quality_dimension():
    cases = [
        EvaluationCase(id="1", category="campaign", question="制定新品活动", expected_intent="campaign_planning", expected_tools=["generate_campaign_plan"], expected_goal="新品冷启动", expected_risk="medium"),
        EvaluationCase(id="2", category="ads", question="广告 ROI", expected_intent="ad_review", expected_tools=["detect_anomalies"], expected_risk="high"),
    ]
    report = await evaluate_cases(cases, PerfectAgent().analyze_case)

    assert report.total_cases == 2
    assert report.intent_accuracy == 100
    assert report.tool_accuracy == 100
    assert report.parameter_accuracy == 100
    assert report.evidence_accuracy == 100
    assert report.risk_accuracy == 100
    assert report.fallback_success_rate == 100
    assert report.mean_latency_ms >= 0
    assert report.p95_latency_ms >= 0


@pytest.mark.parametrize("question,tool", [
    ("进行 RFM 客户分层", "analyze_customer_rfm"),
    ("对比本店和竞品价格", "analyze_competitor_price"),
    ("分析曝光到支付漏斗", "analyze_conversion_funnel"),
    ("活动前检查库存风险", "detect_anomalies"),
    ("制定清仓库存活动方案", "generate_campaign_plan"),
    ("分析会员复购情况", "analyze_customer_rfm"),
    ("哪个转化环节流失最大", "analyze_conversion_funnel"),
])
def test_deterministic_agent_routes_advanced_analysis_tools(question, tool):
    result = EcommerceAgent(EcommerceDataLoader().load_cached()).analyze(question)
    assert tool in [step.tool_name for step in result.tool_trace]
