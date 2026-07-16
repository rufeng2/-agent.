from dataclasses import dataclass

from backend.ecommerce.agent import EcommerceAgent
from backend.ecommerce.schemas import EcommerceDataset, Evidence, ToolTraceStep
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
            if "漏斗" in question or "转化" in question:
                tools.append("analyze_conversion_funnel")
            if "预测" in question or "趋势" in question:
                tools.append("forecast_gmv")
            return tuple(tools)
        if self.role == "product":
            tools = ["rank_products"]
            if "库存" in question or "风险" in question:
                tools.append("detect_anomalies")
            if "竞品" in question or "价格" in question:
                tools.append("analyze_competitor_price")
            return tuple(tools)
        return self.allowed_tools


class MultiAgentCoordinator:
    def __init__(self, dataset: EcommerceDataset):
        self.dataset = dataset

    def route(self, question: str) -> list[str]:
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
        traces = [trace for report in reports for trace in report.tool_trace]
        evidence = [item for report in reports for item in report.evidence]
        analysis.tool_trace = traces or analysis.tool_trace
        analysis.evidence = evidence or analysis.evidence
        analysis.summary = " ".join(report.summary for report in reports if report.summary)
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
