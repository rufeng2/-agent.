from backend.ecommerce.metrics import safe_div
from backend.ecommerce.schemas import CampaignEffect, EcommerceDataset


def analyze_campaign_effect(dataset: EcommerceDataset) -> CampaignEffect:
    attributed = round(sum(row.attributed_gmv for row in dataset.campaigns), 2)
    baseline = round(sum(row.baseline_gmv for row in dataset.campaigns), 2)
    cost = round(sum(row.discount_cost for row in dataset.campaigns), 2)
    incremental = round(attributed - baseline, 2)
    return CampaignEffect(
        campaign_count=len({row.campaign_id for row in dataset.campaigns}),
        attributed_gmv=attributed,
        baseline_gmv=baseline,
        incremental_gmv=incremental,
        discount_cost=cost,
        roi=round(safe_div(incremental, cost), 2),
    )
