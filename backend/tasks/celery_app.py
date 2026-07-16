"""
Celery 异步任务应用
处理文档解析、索引构建等耗时操作
"""
from celery import Celery
from backend.utils.logger import logger
from backend.config import settings

# 需要放在顶层导入
celery_app = Celery(
    "ecommerce_agent",
    broker=settings.RABBITMQ_URL,
    backend=settings.REDIS_URL,
    include=[
        "backend.tasks.parse_task",
        "backend.tasks.index_task",
        "backend.tasks.evaluation_task",
        "backend.tasks.cleanup_task",
        "backend.tasks.ecommerce_agent_task",
        "backend.tasks.ecommerce_automation_task",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={"backend.tasks.ecommerce_agent_task.run_ecommerce_agent": {"queue": settings.AGENT_CELERY_QUEUE}},
)


celery_app.conf.beat_schedule = {
    "daily-retention-cleanup": {
        "task": "backend.tasks.cleanup_task.cleanup_expired_data",
        "schedule": 86400.0,
    },
    "ecommerce-agent-heartbeat": {
        "task": "backend.tasks.ecommerce_automation_task.run_due_automations",
        "schedule": 60.0,
    },
}
