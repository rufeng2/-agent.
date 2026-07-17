from backend.middleware.production import normalized_route


def test_uuid_and_numeric_paths_have_bounded_metric_labels():
    assert normalized_route("/api/documents/123e4567-e89b-12d3-a456-426614174000/chunks/42") == "/api/documents/{id}/chunks/{id}"


def test_static_paths_are_preserved():
    assert normalized_route("/api/health/ready") == "/api/health/ready"


def test_locust_profile_exercises_ecommerce_agent_routes():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    locustfile = (root / "tests" / "load" / "locustfile.py").read_text(encoding="utf-8")

    assert "EcommerceAgentUser" in locustfile
    assert "/api/ecommerce/dashboard" in locustfile
    assert "/api/documents/list" not in locustfile


def test_prometheus_configuration_uses_ecommerce_agent_names():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    prometheus = (root / "ops" / "prometheus" / "prometheus.yml").read_text(encoding="utf-8")
    alerts = (root / "ops" / "prometheus" / "alerts.yml").read_text(encoding="utf-8")
    dashboard = (root / "ops" / "grafana" / "dashboards" / "rag-operations.json").read_text(encoding="utf-8")

    assert "job_name: ecommerce-agent" in prometheus
    assert "knowledge-rag" not in prometheus
    assert "Ecommerce Agent Operations" in dashboard
    assert "rag_" not in alerts.lower()


def test_runtime_metrics_use_ecommerce_prefix():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    middleware = (root / "backend" / "middleware" / "production.py").read_text(encoding="utf-8")
    observability = (root / "backend" / "services" / "observability.py").read_text(encoding="utf-8")

    assert "ecommerce_http_requests_total" in middleware
    assert "ecommerce_stage_duration_seconds" in observability
    assert "rag_http_requests_total" not in middleware
