import asyncio

from fastapi.testclient import TestClient

import backend.api.ecommerce as ecommerce_api
from backend.ecommerce.persistence.repository import EcommerceRepository
from backend.main import app


def _repository(tmp_path, monkeypatch):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'simulation.db'}")
    asyncio.run(repository.initialize())
    monkeypatch.setattr(ecommerce_api, "_repository", repository)
    monkeypatch.setattr(ecommerce_api, "_repository_ready", True)
    return repository


def test_advance_changes_products_and_shared_api_dataset(tmp_path, monkeypatch):
    repository = _repository(tmp_path, monkeypatch)
    with TestClient(app) as client:
        initial_state = client.get("/api/ecommerce/simulation/state").json()["data"]
        initial_products = client.get("/api/ecommerce/products").json()["data"]
        advanced = client.post("/api/ecommerce/simulation/advance", json={"expected_version": initial_state["version"]}).json()["data"]
        products = client.get("/api/ecommerce/products").json()["data"]
        dashboard = client.get("/api/ecommerce/dashboard").json()["data"]
        campaign = client.get("/api/ecommerce/campaigns/plan", params={"goal": "大促增长"}).json()["data"]

    assert advanced["step"] == 1
    assert advanced["events"]
    assert any(before["gmv"] != after["gmv"] for before, after in zip(initial_products, products))
    assert dashboard["date"] == advanced["current_date"]
    by_id = {item["product_id"]: item for item in products}
    for item in campaign["hero_products"] + campaign["clearance_products"]:
        assert item["gmv"] == by_id[item["product_id"]]["gmv"]
    asyncio.run(repository.dispose())


def test_simulation_state_persists_refresh_and_reset_restores_baseline(tmp_path, monkeypatch):
    repository = _repository(tmp_path, monkeypatch)
    with TestClient(app) as client:
        initial = client.get("/api/ecommerce/simulation/state").json()["data"]
        baseline = client.get("/api/ecommerce/products").json()["data"]
        advanced = client.post("/api/ecommerce/simulation/advance", json={"expected_version": initial["version"]}).json()["data"]
        refreshed = client.get("/api/ecommerce/simulation/state").json()["data"]
        reset = client.post("/api/ecommerce/simulation/reset", json={"expected_version": advanced["version"]}).json()["data"]
        restored = client.get("/api/ecommerce/products").json()["data"]

    assert refreshed["step"] == 1
    assert reset["step"] == 0
    assert [item["gmv"] for item in restored] == [item["gmv"] for item in baseline]
    asyncio.run(repository.dispose())


def test_simulation_rejects_stale_advance(tmp_path, monkeypatch):
    repository = _repository(tmp_path, monkeypatch)
    with TestClient(app) as client:
        state = client.get("/api/ecommerce/simulation/state").json()["data"]
        assert client.post("/api/ecommerce/simulation/advance", json={"expected_version": state["version"]}).status_code == 200
        stale = client.post("/api/ecommerce/simulation/advance", json={"expected_version": state["version"]})

    assert stale.status_code == 409
    asyncio.run(repository.dispose())
