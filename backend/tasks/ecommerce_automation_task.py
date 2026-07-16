import asyncio

from backend.config import settings
from backend.ecommerce.automation import AutomationService
from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.llm import configured_team_planner
from backend.ecommerce.persistence.repository import EcommerceRepository
from backend.tasks.celery_app import celery_app


@celery_app.task(name="backend.tasks.ecommerce_automation_task.run_due_automations")
def run_due_automations(workspace_id: str = "workspace-demo"):
    async def execute():
        repository = EcommerceRepository(settings.ECOMMERCE_DATABASE_URL)
        await repository.initialize()
        service = AutomationService(repository, EcommerceDataLoader().load_cached(), configured_team_planner())
        results = []
        try:
            for rule in await service.due_rules(workspace_id):
                job = await service.trigger(rule.id, workspace_id)
                result = await service.job_service.run_inline(job.id, workspace_id)
                results.append({"rule_id": rule.id, "job_id": job.id, "status": result.get("status")})
            return results
        finally:
            await repository.dispose()
    return asyncio.run(execute())
