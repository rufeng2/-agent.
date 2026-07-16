from backend.ecommerce.schemas import AgentAnalysis, EcommerceDataset, Evidence, RecommendedAction
from backend.ecommerce.tools import EcommerceTools


class EcommerceAgent:
    def __init__(self, dataset: EcommerceDataset):
        self.dataset = dataset
        self.tools = EcommerceTools(dataset)

    def analyze(self, question: str) -> AgentAnalysis:
        intent = self._detect_intent(question)
        if intent == "campaign_planning":
            return self._campaign(question)
        if intent == "ad_review":
            return self._ad_review(question)
        if intent == "inventory_risk":
            return self._inventory(question)
        return self._business_diagnosis(question)

    def _detect_intent(self, question: str) -> str:
        if any(word in question for word in ["大促", "活动", "参加"]):
            return "campaign_planning"
        if any(word in question for word in ["广告", "ROI", "投放", "预算"]):
            return "ad_review"
        if any(word in question for word in ["库存", "补货"]):
            return "inventory_risk"
        return "business_diagnosis"

    def _business_diagnosis(self, question: str) -> AgentAnalysis:
        dashboard, kpi_trace = self.tools.get_kpi_snapshot()
        attribution, attribution_trace = self.tools.explain_gmv_attribution()
        anomalies, anomaly_trace = self.tools.detect_anomalies()
        _products, product_trace = self.tools.rank_products()
        evidence = [item for anomaly in anomalies for item in anomaly.evidence][:6]
        evidence.extend([
            Evidence(
                label=item.label,
                value=f"{item.delta_value} 元",
                baseline=f"贡献度 {item.contribution_pct}%",
                rule=item.insight,
            )
            for item in attribution
        ])
        recommendations = [
            RecommendedAction.create(
                title="暂停低 ROI 广告计划并复盘素材",
                action_type="ad_budget_pause",
                risk_level="high",
                reason="广告 ROI 异常低于投放阈值，继续消耗会放大损耗。",
                expected_impact="减少低效花费，优先保住整体 ROI。",
                evidence=evidence[:3],
            ),
            RecommendedAction.create(
                title="优化主推商品详情页和评价解释",
                action_type="content_optimization",
                risk_level="low",
                reason="主推商品流量稳定但成交下滑，评价和尺码问题影响转化。",
                expected_impact="提升详情页承接和客服解释效率。",
                evidence=evidence[:4],
            ),
        ]
        return AgentAnalysis(
            question=question,
            intent="business_diagnosis",
            summary=(
                f"GMV 下滑主要由转化率走弱、低 ROI 广告消耗和部分商品库存/评价风险共同造成。"
                f"当前 GMV 为 {dashboard.kpis['gmv'].value} 元，环比 {dashboard.kpis['gmv'].delta_pct}%。"
            ),
            tool_trace=[kpi_trace, attribution_trace, anomaly_trace, product_trace],
            evidence=evidence,
            recommendations=recommendations,
            risk_level="high",
            confidence=0.88,
        )

    def _campaign(self, question: str) -> AgentAnalysis:
        goal = _campaign_goal(question)
        plan, plan_trace = self.tools.generate_campaign_plan(goal)
        products, product_trace = self.tools.rank_products()
        evidence = [
            Evidence(label="主推商品数", value=str(len(plan["hero_products"])), rule="segment in hero/profit"),
            Evidence(label="商品分层样本", value=str(len(products)), rule="gmv + margin + risk tags + ABC"),
        ]
        return AgentAnalysis(
            question=question,
            intent="campaign_planning",
            summary="活动建议采用主推款承接搜索流量、利润款承担满减、风险款先处理库存和评价后再放量。",
            tool_trace=[plan_trace, product_trace],
            evidence=evidence,
            recommendations=[
                RecommendedAction.create("创建周末增长活动方案", "campaign_plan", "medium", "商品分层已完成，具备活动编排条件。", "提升活动选品效率。", evidence)
            ],
            risk_level="medium",
            confidence=0.82,
        )

    def _ad_review(self, question: str) -> AgentAnalysis:
        anomalies, anomaly_trace = self.tools.detect_anomalies()
        ad_evidence = [item for anomaly in anomalies if anomaly.metric == "ad_roi" for item in anomaly.evidence]
        return AgentAnalysis(
            question=question,
            intent="ad_review",
            summary="低 ROI 广告计划应先降预算或暂停，保留 ROI 稳定的商品承接计划。",
            tool_trace=[anomaly_trace],
            evidence=ad_evidence,
            recommendations=[
                RecommendedAction.create("暂停低 ROI 广告计划", "ad_budget_pause", "high", "ROI 低于 1.8 阈值。", "降低无效消耗。", ad_evidence[:2]),
                RecommendedAction.create("复盘低效广告素材和关键词", "content_optimization", "low", "点击消耗未转化为足够成交。", "提升后续投放素材质量。", ad_evidence[:2]),
            ],
            risk_level="high",
            confidence=0.8,
        )
    def _inventory(self, question: str) -> AgentAnalysis:
        anomalies, anomaly_trace = self.tools.detect_anomalies()
        stock_evidence = [item for anomaly in anomalies if anomaly.metric == "inventory" for item in anomaly.evidence]
        return AgentAnalysis(
            question=question,
            intent="inventory_risk",
            summary="库存风险集中在安全库存以下的主推或新品，建议先补货再放量。",
            tool_trace=[anomaly_trace],
            evidence=stock_evidence,
            recommendations=[
                RecommendedAction.create("为低库存商品创建补货任务", "campaign_plan", "medium", "库存低于安全线。", "降低活动断货风险。", stock_evidence[:2])
            ],
            risk_level="medium",
            confidence=0.78,
        )


def _campaign_goal(question: str) -> str:
    for goal in ("新品冷启动", "清仓库存", "会员复购", "大促增长"):
        if goal in question:
            return goal
    if "新品" in question or "上新" in question:
        return "新品冷启动"
    if "清仓" in question or "尾货" in question:
        return "清仓库存"
    if "会员" in question or "复购" in question or "老客" in question:
        return "会员复购"
    return "大促增长"
