from backend.config import settings
from backend.tasks.ecommerce_agent_task import run_ecommerce_agent
from backend.tasks.celery_app import celery_app


def test_celery_task_is_routed_to_ecommerce_queue():
    route = celery_app.conf.task_routes["backend.tasks.ecommerce_agent_task.run_ecommerce_agent"]
    assert route["queue"] == settings.AGENT_CELERY_QUEUE
    assert run_ecommerce_agent.name == "backend.tasks.ecommerce_agent_task.run_ecommerce_agent"


def test_development_runtime_defaults_to_inline_execution():
    assert settings.AGENT_EXECUTION_MODE in {"inline", "celery"}


def test_celery_beat_schedules_ecommerce_heartbeat():
    schedule = celery_app.conf.beat_schedule["ecommerce-agent-heartbeat"]
    assert schedule["task"] == "backend.tasks.ecommerce_automation_task.run_due_automations"
    assert schedule["schedule"] == 60.0
