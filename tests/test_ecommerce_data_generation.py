import hashlib
from pathlib import Path

from backend.ecommerce.data_loader import EcommerceDataLoader
from scripts.generate_ecommerce_data import generate_dataset


def _file_hashes(root: Path) -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.iterdir())
        if path.is_file()
    }


def test_generator_creates_reproducible_ninety_day_dataset(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"

    generate_dataset(first, days=90, seed=20260716)
    generate_dataset(second, days=90, seed=20260716)

    assert _file_hashes(first) == _file_hashes(second)
    dataset = EcommerceDataLoader(first).load()
    assert len({row.date for row in dataset.orders}) == 90
    assert len({row.date for row in dataset.funnel}) == 90
    assert dataset.customers
    assert dataset.campaigns


def test_generated_dataset_has_valid_references(tmp_path):
    output = tmp_path / "dataset"
    generate_dataset(output)
    dataset = EcommerceDataLoader(output).load()

    product_ids = {item.product_id for item in dataset.products}
    customer_ids = {item.customer_id for item in dataset.customers}
    assert {row.product_id for row in dataset.orders} <= product_ids
    assert {row.product_id for row in dataset.funnel} <= product_ids
    assert {row.customer_id for row in dataset.orders if row.customer_id} <= customer_ids
    assert {row.product_id for row in dataset.campaigns} <= product_ids
