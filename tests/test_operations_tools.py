from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.operations_tools import SandboxOperationsTools


def test_competitor_snapshot_has_traceable_evidence():
    tools = SandboxOperationsTools(EcommerceDataLoader().load_cached())
    snapshot = tools.competitor_snapshot("P003", days=30, channel="小红书")

    assert snapshot["product"]["name"] == "便携榨汁杯"
    assert snapshot["price_comparison"]["competitor_price"] > 0
    assert snapshot["price_comparison"]["price_gap_pct"] != 0
    assert snapshot["review_signals"]
    assert all(item["source"] for item in snapshot["evidence"])
    assert all(item["sample_size"] > 0 for item in snapshot["evidence"])
