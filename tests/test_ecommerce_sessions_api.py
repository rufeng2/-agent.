import asyncio

from fastapi.testclient import TestClient

import backend.api.ecommerce as ecommerce_api
from backend.ecommerce.persistence.repository import EcommerceRepository
from backend.main import app


def _isolated_repository(tmp_path, monkeypatch):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    asyncio.run(repository.initialize())
    monkeypatch.setattr(ecommerce_api, "_repository", repository)
    monkeypatch.setattr(ecommerce_api, "_repository_ready", True)
    return repository


def test_agent_api_creates_and_restores_multi_turn_session(tmp_path, monkeypatch):
    repository = _isolated_repository(tmp_path, monkeypatch)
    with TestClient(app) as client:
        first = client.post("/api/ecommerce/agent/analyze", json={"question": "昨天 GMV 为什么下降？"}).json()["data"]
        second = client.post("/api/ecommerce/agent/analyze", json={"question": "具体哪些商品有风险？", "session_id": first["session_id"]}).json()["data"]
        detail = client.get(f"/api/ecommerce/sessions/{first['session_id']}").json()["data"]

    assert second["session_id"] == first["session_id"]
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant", "user", "assistant"]
    asyncio.run(repository.dispose())


def test_sessions_can_be_listed_for_demo_user(tmp_path, monkeypatch):
    repository = _isolated_repository(tmp_path, monkeypatch)
    with TestClient(app) as client:
        client.post("/api/ecommerce/agent/analyze", json={"question": "分析库存风险"})
        sessions = client.get("/api/ecommerce/sessions").json()["data"]

    assert sessions
    assert sessions[0]["title"]
    asyncio.run(repository.dispose())
