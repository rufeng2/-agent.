from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import backend.middleware.production as production
from backend.main import app
from backend.utils.auth import create_access_token


@pytest.fixture(autouse=True)
def allow_requests(monkeypatch):
    class DummySession:
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False
        def add(self, _item): return None
        async def commit(self): return None
    monkeypatch.setattr(production, "_allow_request", AsyncMock(return_value=(True, 120, False)))
    monkeypatch.setattr(production, "AsyncSessionLocal", lambda: DummySession())


def headers(username: str, role: str = "user") -> dict:
    return {"Authorization": f"Bearer {create_access_token(username, role)}"}


def test_execution_tasks_are_isolated_by_jwt_workspace():
    with TestClient(app) as client:
        created = client.post("/api/ecommerce/execution/tasks", json={"goal": "下架商品 P003"}, headers=headers("tenant-alice"))
        assert created.status_code == 201
        task_id = created.json()["data"]["id"]

        alice_ids = {item["id"] for item in client.get("/api/ecommerce/execution/tasks", headers=headers("tenant-alice")).json()["data"]}
        bob_ids = {item["id"] for item in client.get("/api/ecommerce/execution/tasks", headers=headers("tenant-bob")).json()["data"]}
        assert task_id in alice_ids
        assert task_id not in bob_ids


def test_viewer_cannot_create_execution_task():
    with TestClient(app) as client:
        response = client.post("/api/ecommerce/execution/tasks", json={"goal": "下架商品 P003"}, headers=headers("readonly", "viewer"))
        assert response.status_code == 403
