import asyncio

from fastapi.testclient import TestClient

import backend.api.ecommerce as ecommerce_api
from backend.ecommerce.observability import sanitize
from backend.ecommerce.persistence.repository import EcommerceRepository
from backend.main import app


def test_sanitizer_redacts_nested_secrets():
    value = sanitize({"Authorization": "Bearer abc", "api_key": "secret", "nested": {"token": "123", "value": 7}})
    assert value["Authorization"] == "[REDACTED]"
    assert value["api_key"] == "[REDACTED]"
    assert value["nested"]["token"] == "[REDACTED]"
    assert value["nested"]["value"] == 7


def test_agent_run_and_summary_are_queryable(tmp_path, monkeypatch):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    asyncio.run(repository.initialize())
    monkeypatch.setattr(ecommerce_api, "_repository", repository)
    monkeypatch.setattr(ecommerce_api, "_repository_ready", True)

    with TestClient(app) as client:
        analysis = client.post("/api/ecommerce/agent/analyze", json={"question": "昨天 GMV 为什么下降？"}).json()["data"]
        runs = client.get("/api/ecommerce/runs", params={"execution_mode": "deterministic_fallback"}).json()["data"]
        detail = client.get(f"/api/ecommerce/runs/{analysis['run_id']}").json()["data"]
        summary = client.get("/api/ecommerce/runs/summary").json()["data"]

    assert runs[0]["id"] == analysis["run_id"]
    assert detail["tools"]
    assert detail["total_latency_ms"] >= 0
    assert summary["success_rate"] == 100
    assert summary["fallback_rate"] == 100
    assert summary["p95_latency_ms"] >= 0
    asyncio.run(repository.dispose())
