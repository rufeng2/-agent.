from pathlib import Path

from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.operations_center import build_operations_center


def _center():
    dataset = EcommerceDataLoader(Path("data/ecommerce")).load_cached()
    return build_operations_center(dataset)


def test_operations_center_covers_real_job_responsibilities():
    center = _center()
    assert {item["id"] for item in center["domains"]} == {
        "store_product", "marketing", "analytics", "customer_service",
        "team", "supply_chain", "platform_incident",
    }


def test_daily_tasks_are_actionable_and_measurable():
    tasks = _center()["tasks"]
    assert tasks
    for task in tasks:
        assert task["owner"]
        assert task["deadline"]
        assert task["evidence"]
        assert task["acceptance_metric"]
        assert task["priority"] in {"P0", "P1", "P2"}


def test_center_contains_customer_supply_and_incident_signals():
    center = _center()
    assert center["customer_service"]["refund_rate"] >= 0
    assert center["supply_chain"]["low_stock_skus"] >= 0
    assert center["incident"]["status"] in {"normal", "attention", "critical"}
    assert center["team_workload"]
