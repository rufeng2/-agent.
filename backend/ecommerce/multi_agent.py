from dataclasses import dataclass

from backend.ecommerce.agent import EcommerceAgent
from backend.ecommerce.schemas import EcommerceDataset, Evidence, RecommendedAction, ToolTraceStep
from backend.ecommerce.operation_scenarios import detect_operation_scenario
from backend.ecommerce.tool_registry import EcommerceToolRegistry
from backend.ecommerce.tools import EcommerceTools


ROLE_TOOLS = {
    "data_analyst": ("get_kpi_snapshot", "explain_gmv_attribution", "detect_anomalies", "analyze_conversion_funnel", "forecast_gmv"),
    "product": ("rank_products", "detect_anomalies", "analyze_competitor_price"),
    "customer": ("analyze_customer_rfm",),
    "campaign": ("generate_campaign_plan", "analyze_campaign_effect"),
}


@dataclass
class SpecialistReport:
    agent: str
    summary: str
    tool_trace: list[ToolTraceStep]
    evidence: list[Evidence]
    warnings: list[str]


class SpecialistAgent:
    def __init__(self, role: str, dataset: EcommerceDataset):
        if role not in ROLE_TOOLS:
            raise ValueError(f"Unknown specialist role: {role}")
        self.role = role
        self.allowed_tools = ROLE_TOOLS[role]
        self.registry = EcommerceToolRegistry(EcommerceTools(dataset))

    def execute_tool(self, name: str, arguments: dict):
        if name not in self.allowed_tools:
            raise PermissionError(f"{self.role} cannot execute {name}")
        return self.registry.execute(name, arguments)

    def analyze(self, question: str) -> SpecialistReport:
        traces, evidence, summaries, warnings = [], [], [], []
        for name in self._select_tools(question):
            result, trace = self.execute_tool(name, {"goal": question} if name == "generate_campaign_plan" else {})
            traces.append(trace)
            evidence.extend(result.evidence)
            summaries.append(result.summary)
            warnings.extend(result.warnings)
        return SpecialistReport(self.role, " ".join(summaries), traces, evidence, warnings)

    def _select_tools(self, question: str) -> tuple[str, ...]:
        if self.role == "data_analyst":
            tools = ["get_kpi_snapshot", "explain_gmv_attribution"]
            if any(word in question for word in ("异常", "下降", "广告", "投放", "差评")):
                tools.append("detect_anomalies")
            if "漏斗" in question or "转化" in question:
                tools.append("analyze_conversion_funnel")
            if "预测" in question or "趋势" in question:
                tools.append("forecast_gmv")
            return tuple(tools)
        if self.role == "product":
            tools = ["rank_products"]
            if any(word in question for word in ("库存", "风险", "断货", "补货", "广告", "投放", "差评", "评分")):
                tools.append("detect_anomalies")
            if "竞品" in question or "价格" in question:
                tools.append("analyze_competitor_price")
            return tuple(tools)
        return self.allowed_tools


class MultiAgentCoordinator:
    def __init__(self, dataset: EcommerceDataset):
        self.dataset = dataset

    def route(self, question: str) -> list[str]:
        domain_matches = [
            role for role, keywords in (
                ("product", ("商品", "库存", "补货", "竞品", "价格", "选品")),
                ("customer", ("客户", "用户", "复购", "RFM", "LTV", "会员")),
                ("campaign", ("活动", "大促", "方案", "ROI", "预算")),
            ) if any(word in question for word in keywords)
        ]
        if len(domain_matches) >= 3:
            return ["data_analyst", *domain_matches]
        scenario = detect_operation_scenario(question)
        if scenario:
            return list(scenario.agents)
        selected = ["data_analyst"]
        domains = (
            ("product", ("商品", "库存", "补货", "竞品", "价格", "选品")),
            ("customer", ("客户", "用户", "复购", "RFM", "LTV", "会员")),
            ("campaign", ("活动", "大促", "方案", "ROI", "预算")),
        )
        for role, keywords in domains:
            if any(word in question for word in keywords):
                selected.append(role)
        if len(selected) == 1:
            selected.append("product")
        return selected[:4]

    def run_specialist(self, role: str, question: str) -> SpecialistReport:
        return SpecialistAgent(role, self.dataset).analyze(question)

    def review(self, reports: list[SpecialistReport]) -> dict:
        evidence_count = sum(len(report.evidence) for report in reports)
        warnings = [warning for report in reports for warning in report.warnings]
        return {
            "status": "passed" if evidence_count else "insufficient_evidence",
            "evidence_count": evidence_count,
            "warnings": warnings,
        }

    def synthesize(self, question: str, reports: list[SpecialistReport], review: dict):
        analysis = EcommerceAgent(self.dataset).analyze(question)
        scenario = detect_operation_scenario(question)
        traces = [trace for report in reports for trace in report.tool_trace]
        evidence = [item for report in reports for item in report.evidence]
        analysis.tool_trace = traces or analysis.tool_trace
        analysis.evidence = evidence or analysis.evidence
        analysis.summary = " ".join(report.summary for report in reports if report.summary)
        if scenario:
            analysis.intent = scenario.intent
            analysis.scenario_context = {
                "scenario": scenario.id,
                "pain_point": scenario.pain_point,
                "decision": scenario.decision,
            }
            if scenario.id != "product_recommendation":
                analysis.summary = EcommerceAgent(self.dataset).analyze(question).summary
        if _is_product_recommendation(question):
            product_report = next((report for report in reports if report.agent == "product"), None)
            top_product = product_report.evidence[0] if product_report and product_report.evidence else None
            if top_product:
                analysis.intent = "product_recommendation"
                analysis.summary = f"推荐优先考虑 {top_product.label}。该商品在当前模拟数据中的经营表现排名靠前，适合作为首选商品进一步评估。"
                analysis.evidence = product_report.evidence[:5]
                analysis.recommendations = [RecommendedAction.create(
                    title=f"将 {top_product.label} 纳入主推候选",
                    action_type="product_selection",
                    risk_level="medium",
                    reason="商品经营排序显示其综合表现领先，仍需结合目标渠道和预算进行人工确认。",
                    expected_impact="缩短选品时间，并为后续活动或 Listing 工作流提供候选商品。",
                    evidence=product_report.evidence[:3],
                )]
        analysis.execution_mode = "multi_agent_deterministic"
        analysis.warnings = list(dict.fromkeys(review["warnings"]))
        analysis.agent_trace = [
            {"agent": "supervisor", "status": "completed", "tools": [report.agent for report in reports]},
            *[
                {"agent": report.agent, "status": "completed", "tools": [step.tool_name for step in report.tool_trace]}
                for report in reports
            ],
            {"agent": "risk_reviewer", "status": review["status"], "tools": []},
            {"agent": "report_writer", "status": "completed", "tools": []},
        ]
        return analysis


def _is_product_recommendation(question: str) -> bool:
    return any(phrase in question for phrase in ("选一个商品", "商品推荐", "推荐商品", "推荐一个商品", "选品推荐"))
