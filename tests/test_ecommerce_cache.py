from pathlib import Path

from backend.ecommerce.cache import TTLCache
from backend.ecommerce.data_loader import EcommerceDataLoader
from scripts.generate_ecommerce_data import generate_dataset


def test_dataset_cache_reuses_data_until_source_signature_changes(tmp_path, monkeypatch):
    root = tmp_path / "data"
    generate_dataset(root, days=10)
    loader = EcommerceDataLoader(root)
    calls = 0
    original = loader.load

    def counted_load():
        nonlocal calls
        calls += 1
        return original()

    monkeypatch.setattr(loader, "load", counted_load)
    first = loader.load_cached()
    second = loader.load_cached()
    assert first is second
    assert calls == 1

    products = root / "products.csv"
    products.write_text(products.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    third = loader.load_cached()
    assert third is not first
    assert calls == 2


def test_ttl_cache_recomputes_after_expiration():
    now = [100.0]
    cache = TTLCache(ttl_seconds=10, clock=lambda: now[0])
    calls = 0

    def factory():
        nonlocal calls
        calls += 1
        return calls

    assert cache.get_or_set("dashboard", factory) == 1
    assert cache.get_or_set("dashboard", factory) == 1
    now[0] = 111.0
    assert cache.get_or_set("dashboard", factory) == 2
