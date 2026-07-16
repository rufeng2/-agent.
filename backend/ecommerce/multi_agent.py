from dataclasses import dataclass, field

from backend.ecommerce.agent import EcommerceAgent
from backend.ecommerce.growth_workflow import GrowthWorkflowService
from backend.ecommerce.operation_scenarios import detect_operation_scenario
from backend.ecommerce.schemas import EcommerceDataset, Evidence, RecommendedAction, ToolTraceStep
from backend.ecommerce.segmentation import build_product_analysis
from backend.ecommerce.tool_registry import EcommerceToolRegistry
from backend.ecommerce.tools import EcommerceTools


TEAM_ROLES = ("product_research", "pricing", "listing", "advertising", "customer_service")
ROLE_PROFILES = {
    "product_research": {"title": "选品专员", "mission": "用市场、商品、竞品和评论证据判断产品机会", "tools": ("rank_products", "analyze_competitor_price")},
    "pricing": {"title": "定价专员", "mission": "核算成本、利润空间、价格带和盈亏平衡 ACOS", "tools": ()},
    "listing": {"title": "Listing 专员", "mission": "生成平台标题、五点描述、关键词和合规内容", "tools": ()},
    "advertising": {"title": "推广专员", "mission": "制定广告结构、预算、竞价和效果监控方案", "tools": ("detect_anomalies", "generate_campaign_plan")},
    "customer_service": {"title": "客服专员", "mission": "整理客户问题、FAQ、差评预警和回复策略", "tools": ("analyze_customer_rfm",)},
}


@dataclass
class SpecialistReport:
    agent: str
    summary: str
    tool_trace: list[ToolTraceStep]
    evidence: list[Evidence]
    warnings: list[str]
    deliverable: dict = field(default_factory=dict)


class SpecialistAgent:
    def __init__(self, role: str, dataset: EcommerceDataset):
        if role not in ROLE_PROFILES:
            raise ValueError(f"Unknown specialist role: {role}")
        self.role = role
        self.profile = ROLE_PROFILES[role]
        self.allowed_tools = self.profile["tools"]
        self.dataset = dataset
        self.registry = EcommerceToolRegistry(EcommerceTools(dataset))

    def execute_tool(self, name: str, arguments: dict):
        if name not in self.allowed_tools:
            raise PermissionError(f"{self.role} cannot execute {name}")
        return self.registry.execute(name, arguments)

    def analyze(self, question: str) -> SpecialistReport:
        product = self._target_product()
        if self.role == "product_research":
            ranked, rank_trace = self.execute_tool("rank_products", {})
            competitors, competitor_trace = self.execute_tool("analyze_competitor_price", {})
            top = ranked.evidence[0]
            deliverable = {"recommended_product_id": product.product_id, "recommended_product": product.name, "market_score": 82, "positioning": product.positioning, "competitor_summary": competitors.summary}
            return SpecialistReport(self.role, f"选品建议优先评估 {product.name}，并结合竞品价格和评论信号验证市场机会。", [rank_trace, competitor_trace], [*ranked.evidence[:5], *competitors.evidence[:3]], [], deliverable)
        if self.role == "pricing":
            competitor = next(item for item in self.dataset.competitors if item.product_id == product.product_id)
            recommended = round(max(product.cost * 1.8, min(product.price, competitor.competitor_price * 0.98)), 2)
            margin = round((recommended - product.cost) / recommended * 100, 2)
            break_even_acos = round((recommended - product.cost) / recommended * 100, 2)
            trace = ToolTraceStep(tool_name="calculate_pricing_model", step_title="核算成本、利润和价格带", input={"product_id": product.product_id}, output_summary=f"建议售价 {recommended} 元，预计毛利率 {margin}%。")
            evidence = [Evidence(label="建议售价", value=f"{recommended} 元", baseline=f"当前 {product.price} 元"), Evidence(label="预计毛利率", value=f"{margin}%", rule="售价必须高于成本并保留投放空间")]
            return SpecialistReport(self.role, f"建议售价 {recommended} 元，盈亏平衡 ACOS 约 {break_even_acos}%。", [trace], evidence, [], {"recommended_price": recommended, "cost": product.cost, "gross_margin_rate": margin, "break_even_acos": break_even_acos})
        if self.role == "listing":
            workflow = GrowthWorkflowService(self.dataset).generate(product.product_id, "Amazon US", product.category)
            listing = workflow["listing"]
            trace = ToolTraceStep(tool_name="generate_marketplace_listing", step_title="生成 Amazon Listing", input={"product_id": product.product_id, "platform": "Amazon US"}, output_summary=f"已生成标题、5 条卖点和 {len(listing['search_terms'])} 个搜索词。")
            return SpecialistReport(self.role, "Amazon US Listing 草稿和合规检查已完成。", [trace], [Evidence(label="Listing 合规", value=workflow["compliance"]["status"], rule="绝对化、医疗宣称、标题长度")], workflow["compliance"]["issues"], listing)
        if self.role == "advertising":
            anomalies, anomaly_trace = self.execute_tool("detect_anomalies", {})
            campaign, campaign_trace = self.execute_tool("generate_campaign_plan", {"goal": "新品冷启动" if "新品" in question else "大促增长"})
            deliverable = {"daily_budget": 300, "campaign_structure": ["自动广告采词", "手动广泛拓词", "手动精准承接转化词"], "optimization_rules": ["花费超过目标 CPA 且零转化时降价", "转化率高于 10% 的词转入精准组", "每 3 天复盘搜索词和否定词"]}
            return SpecialistReport(self.role, "采用自动采词、广泛拓词和精准转化三层广告结构，小预算验证后逐步放量。", [anomaly_trace, campaign_trace], [*anomalies.evidence[:3], *campaign.evidence[:3]], campaign.warnings, deliverable)
        topics = list(dict.fromkeys(item.topic for item in self.dataset.reviews if item.product_id == product.product_id))[:5]
        rfm, rfm_trace = self.execute_tool("analyze_customer_rfm", {})
        deliverable = {"faq": [f"如何处理关于“{topic}”的问题？" for topic in topics] or ["如何正确使用和维护商品？"], "reply_policy": "先确认问题与订单信息，再提供解决方案；退款和补发必须保留人工审批。", "alert_rules": ["评分低于 3 星立即预警", "同类问题 24 小时出现 3 次时同步商品专员"]}
        return SpecialistReport(self.role, "已根据评价主题生成 FAQ、回复原则和差评预警规则。", [rfm_trace], rfm.evidence[:3], [], deliverable)

    def _target_product(self):
        top = build_product_analysis(self.dataset)[0]
        return next(item for item in self.dataset.products if item.product_id == top.product_id)


class MultiAgentCoordinator:
    def __init__(self, dataset: EcommerceDataset):
        self.dataset = dataset

    def route(self, question: str) -> list[str]:
        if all(word in question for word in ("商品", "客户", "活动")):
            return list(TEAM_ROLES)
        if any(word in question for word in ("从 0", "从0", "完整方案", "新品上架", "上架一款", "上市方案")):
            return list(TEAM_ROLES)
        scenario = detect_operation_scenario(question)
        if scenario:
            mapping = {
                "product_recommendation": ("product_research",), "stockout_before_campaign": ("product_research", "advertising"),
                "ad_budget_waste": ("advertising", "pricing"), "review_conversion_loss": ("customer_service", "listing"),
                "competitor_price_cut": ("product_research", "pricing"), "customer_churn": ("customer_service", "advertising"),
                "new_product_launch": TEAM_ROLES, "campaign_selection": ("product_research", "advertising"),
                "funnel_loss": ("listing", "advertising"), "gmv_drop": ("product_research", "pricing", "advertising"),
            }
            return list(mapping[scenario.id])
        if any(word in question for word in ("Listing", "标题", "五点", "关键词")):
            return ["product_research", "listing"]
        if any(word in question for word in ("价格", "定价", "利润", "成本")):
            return ["product_research", "pricing"]
        if any(word in question for word in ("广告", "ACOS", "投放")):
            return ["pricing", "advertising"]
        if any(word in question for word in ("客服", "差评", "回复", "FAQ")):
            return ["customer_service"]
        return ["product_research", "pricing", "advertising"]

    def run_specialist(self, role: str, question: str) -> SpecialistReport:
        return SpecialistAgent(role, self.dataset).analyze(question)

    def review(self, reports: list[SpecialistReport]) -> dict:
        evidence_count = sum(len(report.evidence) for report in reports)
        return {"status": "passed" if evidence_count else "insufficient_evidence", "evidence_count": evidence_count, "warnings": [str(w) for report in reports for w in report.warnings]}

    def synthesize(self, question: str, reports: list[SpecialistReport], review: dict):
        analysis = EcommerceAgent(self.dataset).analyze(question)
        scenario = detect_operation_scenario(question)
        analysis.tool_trace = [trace for report in reports for trace in report.tool_trace]
        analysis.evidence = [item for report in reports for item in report.evidence]
        analysis.team_deliverables = {report.agent: report.deliverable for report in reports}
        analysis.summary = "主管已完成任务拆解和专家汇总：" + " ".join(report.summary for report in reports)
        analysis.execution_mode = "openclaw_team_deterministic"
        analysis.warnings = list(dict.fromkeys(review["warnings"]))
        if scenario:
            analysis.intent = scenario.intent
            analysis.scenario_context = {"scenario": scenario.id, "pain_point": scenario.pain_point, "decision": scenario.decision}
            if scenario.id == "product_recommendation":
                chosen = analysis.team_deliverables["product_research"]["recommended_product"]
                analysis.summary = f"推荐优先考虑 {chosen}。选品专员已结合商品经营表现、竞品价格和评论信号完成初步评估。"
        if "product_research" in analysis.team_deliverables:
            chosen = analysis.team_deliverables["product_research"]["recommended_product"]
            analysis.recommendations = [RecommendedAction.create(f"批准 {chosen} 进入下一阶段", "new_product_launch", "high", "五个专员已完成初步方案，需要人工确认成本、内容和预算。", "进入 Listing 审批和沙箱上架流程。", analysis.evidence[:4])]
        analysis.agent_trace = [
            {"agent": "supervisor", "status": "completed", "tools": [report.agent for report in reports]},
            *[{"agent": report.agent, "status": "completed", "tools": [step.tool_name for step in report.tool_trace]} for report in reports],
            {"agent": "supervisor_summary", "status": review["status"], "tools": []},
        ]
        return analysis
