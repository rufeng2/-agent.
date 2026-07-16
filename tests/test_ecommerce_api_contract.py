from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import backend.middleware.production as production
from backend.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def allow_requests(monkeypatch):
    class DummySession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def add(self, _item):
            return None

        async def commit(self):
            return None

    monkeypatch.setattr(production, "_allow_request", AsyncMock(return_value=(True, 120, False)))
    monkeypatch.setattr(production, "AsyncSessionLocal", lambda: DummySession())


def test_ecommerce_dashboard_endpoint_returns_kpis():
    response = client.get("/api/ecommerce/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert "gmv" in payload["data"]["kpis"]
    assert payload["data"]["anomalies"]


def test_mcp_status_exposes_real_server_tools():
    response = client.get("/api/ecommerce/mcp/status")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "ready"
    assert data["transport"] == "stdio"
    assert "update_product_price" in {tool["name"] for tool in data["tools"]}


def test_ecommerce_agent_endpoint_returns_trace_and_recommendations():
    response = client.post("/api/ecommerce/agent/analyze", json={"question": "昨天 GMV 为什么下降？"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "business_diagnosis"
    assert data["tool_trace"]
    assert data["recommendations"]


def test_recommendation_approval_flow():
    created = client.post("/api/ecommerce/agent/analyze", json={"question": "哪些广告计划 ROI 太低？"}).json()["data"]
    recommendation_id = created["recommendations"][0]["id"]

    approved = client.post(f"/api/ecommerce/recommendations/{recommendation_id}/approve").json()["data"]

    assert approved["status"] == "approved"


def test_execution_agent_creates_approves_and_rolls_back_task():
    created_response = client.post("/api/ecommerce/execution/tasks", json={"goal": "把轻量跑步鞋价格调整到280元"})
    assert created_response.status_code == 201
    created = created_response.json()["data"]
    assert created["status"] == "waiting_approval"
    assert created["state"]["specialist"] == "pricing_agent"

    completed_response = client.post(
        f"/api/ecommerce/execution/tasks/{created['id']}/approve",
        json={"expected_version": created["version"], "comment": "API contract"},
    )
    assert completed_response.status_code == 200
    completed = completed_response.json()["data"]
    assert completed["status"] == "completed"
    assert completed["result"]["after"]["price"] == 280
    assert completed["result"]["mcp"]["tool"] == "update_product_price"

    rolled_back = client.post(
        f"/api/ecommerce/execution/tasks/{created['id']}/rollback",
        json={"expected_version": completed["version"], "comment": "rollback"},
    ).json()["data"]
    assert rolled_back["status"] == "rolled_back"


def test_campaign_plan_uses_selected_goal():
    response = client.get("/api/ecommerce/campaigns/plan", params={"goal": "新品冷启动"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["goal"] == "新品冷启动"
    assert data["theme"] == "新品冷启动策略"
    assert data["tool_trace"][0]["input"]["goal"] == "新品冷启动"


def test_campaign_plan_changes_products_for_selected_goal():
    growth = client.get("/api/ecommerce/campaigns/plan", params={"goal": "大促增长"}).json()["data"]
    launch = client.get("/api/ecommerce/campaigns/plan", params={"goal": "新品冷启动"}).json()["data"]
    clearance = client.get("/api/ecommerce/campaigns/plan", params={"goal": "清仓库存"}).json()["data"]
    repurchase = client.get("/api/ecommerce/campaigns/plan", params={"goal": "会员复购"}).json()["data"]

    growth_ids = [item["product_id"] for item in growth["hero_products"]]
    launch_ids = [item["product_id"] for item in launch["hero_products"]]
    clearance_ids = [item["product_id"] for item in clearance["hero_products"]]

    assert launch_ids != growth_ids
    assert clearance_ids != growth_ids
    assert launch_ids[0] == "P006"
    assert clearance_ids[0] == "P005"
    assert all("差评风险" not in item["risk_tags"] for item in repurchase["hero_products"])
    assert not set(clearance_ids).intersection(item["product_id"] for item in clearance["clearance_products"])
