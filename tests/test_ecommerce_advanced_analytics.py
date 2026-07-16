from pathlib import Path

from backend.ecommerce.campaign_effect import analyze_campaign_effect
from backend.ecommerce.competitors import analyze_competitor_prices
from backend.ecommerce.customers import analyze_rfm
from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.forecast import forecast_gmv
from backend.ecommerce.funnel import analyze_funnel
from backend.ecommerce.tools import EcommerceTools


def _dataset():
    return EcommerceDataLoader(Path("data/ecommerce")).load()


def test_conversion_funnel_is_monotonic_and_has_stage_rates():
    result = analyze_funnel(_dataset())
    values = [stage.value for stage in result.stages]

    assert values == sorted(values, reverse=True)
    assert result.overall_conversion_rate > 0
    assert all(0 <= stage.conversion_from_previous <= 100 for stage in result.stages)


def test_rfm_assigns_every_purchasing_customer_to_one_segment():
    dataset = _dataset()
    result = analyze_rfm(dataset)

    purchasing_customers = {row.customer_id for row in dataset.orders if row.customer_id}
    assert sum(result.segment_counts.values()) == len(purchasing_customers)
    assert {item.customer_id for item in result.customers} == purchasing_customers
    assert result.repeat_purchase_rate > 0
    assert result.average_ltv > 0


def test_campaign_effect_quantifies_incremental_value_and_roi():
    result = analyze_campaign_effect(_dataset())

    assert result.campaign_count > 0
    assert result.incremental_gmv == round(result.attributed_gmv - result.baseline_gmv, 2)
    assert result.roi == round(result.incremental_gmv / result.discount_cost, 2)


def test_competitor_analysis_returns_latest_price_gap_for_each_product():
    result = analyze_competitor_prices(_dataset())

    assert len(result) == len(_dataset().products)
    assert all(item.competitor_price > 0 for item in result)
    assert all(item.price_index > 0 for item in result)


def test_forecast_returns_seven_future_days_with_bounds():
    result = forecast_gmv(_dataset(), horizon=7)

    assert len(result.points) == 7
    assert all(point.lower <= point.predicted_gmv <= point.upper for point in result.points)
    assert result.method == "linear_trend_7d_seasonality"


def test_advanced_analytics_are_exposed_as_normalized_tools():
    tools = EcommerceTools(_dataset())

    for result, trace in [
        tools.analyze_conversion_funnel(),
        tools.analyze_customer_rfm(),
        tools.analyze_campaign_effect(),
        tools.analyze_competitor_price(),
        tools.forecast_gmv(),
    ]:
        assert result.tool_name == trace.tool_name
        assert result.metrics
        assert result.summary
