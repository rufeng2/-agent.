import asyncio

from backend.config import settings
from backend.db.session import AsyncSessionLocal
from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.persistence.repository import EcommerceRepository
from backend.ecommerce.runtime.service import EcommerceJobService
from backend.tasks.celery_app import celery_app


@celery_app.task(
    bind=True,
    name="backend.tasks.ecommerce_agent_task.run_ecommerce_agent",
    autoretry_for=(TimeoutError,),
    retry_backoff=True,
    max_retries=2,
    time_limit=settings.AGENT_JOB_TIME_LIMIT_SECONDS,
)
def run_ecommerce_agent(self, job_id: str, workspace_id: str = "workspace-demo"):
    async def execute():
        repository = EcommerceRepository(settings.ECOMMERCE_DATABASE_URL)
        await repository.initialize()
        try:
            return await EcommerceJobService(repository, EcommerceDataLoader().load_cached()).run_inline(job_id, workspace_id)
        finally:
            await repository.dispose()

    return asyncio.run(execute())
