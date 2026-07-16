from uuid import uuid4

from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.persistence.repository import EcommerceRepository
from backend.ecommerce.runtime.graph import EcommerceGraphRuntime


class EcommerceJobService:
    def __init__(self, repository: EcommerceRepository, dataset=None):
        self.repository = repository
        self.dataset = dataset or EcommerceDataLoader().load_cached()

    async def create_job(self, question: str, workspace_id: str, session_id: str, idempotency_key: str):
        return await self.repository.create_agent_job(str(uuid4()), workspace_id, session_id, idempotency_key, question)

    async def cancel(self, job_id: str, workspace_id: str):
        return await self.repository.cancel_agent_job(job_id, workspace_id)

    async def run_inline(self, job_id: str, workspace_id: str = "workspace-1"):
        job = await self.repository.get_agent_job(job_id, workspace_id)
        if not job:
            raise KeyError(job_id)
        if job.cancelled:
            return {"status": "cancelled"}
        await self.repository.set_agent_job_status(job.id, "running")
        await self.repository.append_agent_event(job.id, "planning_started", {})
        result = await EcommerceGraphRuntime(self.dataset, is_cancelled=lambda: False).run(job.question, [], workspace_id=workspace_id, run_id=job.run_id)
        status = result.get("status", "failed")
        await self.repository.set_agent_job_status(job.id, status)
        await self.repository.append_agent_event(job.id, "completed" if status == "completed" else status, result.get("analysis") or {})
        return result
