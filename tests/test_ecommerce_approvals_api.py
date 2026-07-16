import asyncio

from fastapi.testclient import TestClient

import backend.api.ecommerce as ecommerce_api
from backend.ecommerce.persistence.repository import EcommerceRepository
from backend.main import app


def test_approval_persists_comment_version_and_audit(tmp_path, monkeypatch):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    asyncio.run(repository.initialize())
    monkeypatch.setattr(ecommerce_api, "_repository", repository)
    monkeypatch.setattr(ecommerce_api, "_repository_ready", True)

    with TestClient(app) as client:
        analysis = client.post("/api/ecommerce/agent/analyze", json={"question": "哪些广告 ROI 太低？"}).json()["data"]
        recommendation_id = analysis["recommendations"][0]["id"]
        approved = client.post(
            f"/api/ecommerce/recommendations/{recommendation_id}/approve",
            json={"expected_version": 1, "comment": "同意暂停", "idempotency_key": "web-approve-1"},
        ).json()["data"]
        detail = client.get(f"/api/ecommerce/recommendations/{recommendation_id}").json()["data"]

    assert approved["status"] == "approved"
    assert approved["version"] == 2
    assert detail["approvals"][0]["comment"] == "同意暂停"
    asyncio.run(repository.dispose())
