from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_pytest_only_collects_tests_directory():
    config = (ROOT / "pytest.ini").read_text(encoding="utf-8")
    assert "testpaths = tests" in config
    assert "pythonpath = ." in config


def test_production_image_runs_as_non_root():
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    assert "USER app" in dockerfile
    assert "--reload" not in dockerfile


def test_dockerfile_does_not_require_untracked_local_wheels():
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY backend/wheels" not in dockerfile
    assert "pip install --no-index" not in dockerfile


def test_production_compose_has_no_reload_or_source_mount():
    compose = yaml.safe_load((ROOT / "docker-compose.production.yml").read_text(encoding="utf-8"))
    backend = compose["services"]["backend"]
    command = " ".join(backend.get("command", [])) if isinstance(backend.get("command"), list) else str(backend.get("command", ""))
    assert "--reload" not in command
    assert all("./backend:/app/backend" not in str(item) for item in backend.get("volumes", []))
    assert backend["read_only"] is True


def test_ci_installs_runtime_dependencies_and_scans():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "backend/requirements.txt" in workflow
    assert "backend/requirements-langchain.txt" in workflow
    assert "COMPOSE_PROJECT_NAME: ecommerce-agent" in workflow
    assert "cp .env.example .env" in workflow
    assert "pip-audit" in workflow
    assert "gitleaks" in workflow
    assert "GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in workflow
    assert "fetch-depth: 0" in workflow


def test_runtime_dependencies_do_not_include_known_vulnerable_jose_or_pdf_packages():
    requirements = (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "python-jose" not in requirements
    assert "pypdf2" not in requirements
    assert "pyjwt[crypto]" in requirements
    assert "pypdf>=" in requirements


def test_primary_compose_and_environment_use_ecommerce_names():
    compose_text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    production = (ROOT / "docker-compose.production.yml").read_text(encoding="utf-8")

    assert "ecommerce_ops" in compose_text + env
    assert "ecommerce-agent-backend" in compose_text + production
    assert "container_name: rag-" not in compose_text
    assert "ECOMMERCE_DATABASE_URL" in env


def test_primary_compose_does_not_reference_missing_celery_module():
    compose_text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    celery_module = ROOT / "backend" / "tasks" / "celery_app.py"
    assert "backend.tasks.celery_app" not in compose_text or celery_module.exists()


def test_postgres_healthcheck_uses_configured_database_identity():
    compose_text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "pg_isready -U $${POSTGRES_USER" in compose_text
    assert "-d $${POSTGRES_DB" in compose_text
