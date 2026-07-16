from datetime import date, datetime, timezone
from uuid import uuid4

from pydantic import BaseModel


class ProductRecord(BaseModel):
    product_id: str
    name: str
    category: str
    price: float
    cost: float
    launch_date: date
    positioning: str


class OrderRecord(BaseModel):
    date: date
    product_id: str
    orders: int
    units: int
    gmv: float
    refund_amount: float
    customer_id: str = ""


class TrafficRecord(BaseModel):
    date: date
    product_id: str
    impressions: int
    visitors: int
    add_to_cart: int


class AdSpendRecord(BaseModel):
    date: date
    campaign_id: str
    product_id: str
    channel: str
    spend: float
    attributed_gmv: float
    clicks: int


class InventoryRecord(BaseModel):
    product_id: str
    stock: int
    safety_stock: int
    inbound_units: int
    lead_time_days: int


class ReviewRecord(BaseModel):
    date: date
    product_id: str
    rating: float
    topic: str
    comment_count: int


class CompetitorRecord(BaseModel):
    date: date
    product_id: str
    competitor_price: float
    competitor_promo: str


class CustomerRecord(BaseModel):
    customer_id: str
    registered_at: date
    region: str
    member_level: str


class FunnelRecord(BaseModel):
    date: date
    product_id: str
    impressions: int
    clicks: int
    visitors: int
    add_to_cart: int
    checkout: int
    paid_orders: int
    refunded_orders: int


class CampaignRecord(BaseModel):
    campaign_id: str
    date: date
    product_id: str
    campaign_type: str
    discount_cost: float
    attributed_gmv: float
    baseline_gmv: float


class OperationRules(BaseModel):
    thresholds: dict[str, float]
    risk_actions: dict[str, str]


class EcommerceDataset(BaseModel):
    products: list[ProductRecord]
    orders: list[OrderRecord]
    traffic: list[TrafficRecord]
    ad_spend: list[AdSpendRecord]
    inventory: list[InventoryRecord]
    reviews: list[ReviewRecord]
    competitors: list[CompetitorRecord]
    customers: list[CustomerRecord] = []
    funnel: list[FunnelRecord] = []
    campaigns: list[CampaignRecord] = []
    rules: OperationRules


class KpiValue(BaseModel):
    label: str
    value: float
    unit: str = ""
    delta_pct: float = 0
    trend: str = "flat"


class Evidence(BaseModel):
    label: str
    value: str
    baseline: str = ""
    rule: str = ""


class Anomaly(BaseModel):
    id: str
    metric: str
    title: str
    severity: str
    summary: str
    evidence: list[Evidence]


class GmvAttribution(BaseModel):
    factor: str
    label: str
    current: float
    baseline: float
    delta_value: float
    contribution_pct: float
    insight: str


class DashboardSummary(BaseModel):
    date: str
    kpis: dict[str, KpiValue]
    anomalies: list[Anomaly]
    trend: list[dict[str, float | str]]
    gmv_attribution: list[GmvAttribution]


class ProductAnalysis(BaseModel):
    product_id: str
    name: str
    category: str
    segment: str
    abc_segment: str
    gmv: float
    orders: int
    conversion_rate: float
    gross_margin_rate: float
    stock: int
    safety_stock: int
    inventory_turnover_days: float
    ad_roi: float
    average_rating: float
    risk_tags: list[str]


class FunnelStage(BaseModel):
    name: str
    value: int
    conversion_from_previous: float


class FunnelAnalysis(BaseModel):
    stages: list[FunnelStage]
    overall_conversion_rate: float


class RfmCustomer(BaseModel):
    customer_id: str
    recency_days: int
    frequency: int
    monetary: float
    segment: str


class RfmAnalysis(BaseModel):
    customers: list[RfmCustomer]
    segment_counts: dict[str, int]
    repeat_purchase_rate: float
    average_ltv: float


class CampaignEffect(BaseModel):
    campaign_count: int
    attributed_gmv: float
    baseline_gmv: float
    incremental_gmv: float
    discount_cost: float
    roi: float


class CompetitorPriceAnalysis(BaseModel):
    product_id: str
    name: str
    own_price: float
    competitor_price: float
    price_gap: float
    price_index: float
    competitor_promo: str


class ForecastPoint(BaseModel):
    date: str
    predicted_gmv: float
    lower: float
    upper: float


class GmvForecast(BaseModel):
    method: str
    points: list[ForecastPoint]


class ToolTraceStep(BaseModel):
    tool_name: str
    step_title: str = ""
    input: dict[str, str | int | float | bool]
    output_summary: str


class ToolResult(BaseModel):
    tool_name: str
    input: dict[str, str | int | float | bool]
    metrics: dict[str, str | int | float]
    evidence: list[Evidence] = []
    summary: str
    warnings: list[str] = []


class RecommendedAction(BaseModel):
    id: str
    title: str
    action_type: str
    risk_level: str
    reason: str
    expected_impact: str
    evidence: list[Evidence]
    status: str = "pending"
    operator: str = ""
    updated_at: str = ""

    @staticmethod
    def create(
        title: str,
        action_type: str,
        risk_level: str,
        reason: str,
        expected_impact: str,
        evidence: list[Evidence],
    ) -> "RecommendedAction":
        return RecommendedAction(
            id=str(uuid4()),
            title=title,
            action_type=action_type,
            risk_level=risk_level,
            reason=reason,
            expected_impact=expected_impact,
            evidence=evidence,
            updated_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        )


class AgentAnalysis(BaseModel):
    question: str
    intent: str
    summary: str
    tool_trace: list[ToolTraceStep]
    evidence: list[Evidence]
    recommendations: list[RecommendedAction]
    risk_level: str
    confidence: float
