from fastapi.testclient import TestClient

from backend.main import app


def test_liveness_health_endpoint_is_available():
    response = TestClient(app).get("/api/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_health_endpoint_is_available():
    response = TestClient(app).get("/api/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"]["api"] == "ok"
