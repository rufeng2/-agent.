from backend.ecommerce.metrics import safe_div
from backend.ecommerce.schemas import EcommerceDataset, FunnelAnalysis, FunnelStage


def analyze_funnel(dataset: EcommerceDataset) -> FunnelAnalysis:
    totals = {
        "曝光": sum(row.impressions for row in dataset.funnel),
        "点击": sum(row.clicks for row in dataset.funnel),
        "访问": sum(row.visitors for row in dataset.funnel),
        "加购": sum(row.add_to_cart for row in dataset.funnel),
        "结算": sum(row.checkout for row in dataset.funnel),
        "支付": sum(row.paid_orders for row in dataset.funnel),
        "退款后留存": sum(max(0, row.paid_orders - row.refunded_orders) for row in dataset.funnel),
    }
    stages: list[FunnelStage] = []
    previous = 0
    for name, value in totals.items():
        rate = 100.0 if not stages else safe_div(value, previous) * 100
        stages.append(FunnelStage(name=name, value=value, conversion_from_previous=round(rate, 2)))
        previous = value
    return FunnelAnalysis(
        stages=stages,
        overall_conversion_rate=round(safe_div(totals["支付"], totals["曝光"]) * 100, 2),
    )
