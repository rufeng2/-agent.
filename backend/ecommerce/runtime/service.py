from uuid import uuid4

from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.persistence.repository import EcommerceRepository
from backend.ecommerce.runtime.graph import EcommerceGraphRuntime
from backend.ecommerce.agent_memory import DEFAULT_AGENT_MEMORIES, group_memories


class EcommerceJobService:
    def __init__(self, repository: EcommerceRepository, dataset=None, team_planner=None):
        self.repository = repository
        self.dataset = dataset or EcommerceDataLoader().load_cached()
        self.team_planner = team_planner

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
        stored_memories = await self.repository.list_agent_memories(workspace_id)
        if not stored_memories:
            for agent, memories in DEFAULT_AGENT_MEMORIES.items():
                for key, value in memories.items():
                    await self.repository.upsert_agent_memory(workspace_id, agent, key, value, "system")
            stored_memories = await self.repository.list_agent_memories(workspace_id)
        agent_memories = group_memories(stored_memories)
        memory_context = [{"role": "system", "content": f"{agent} memory: {memory}"} for agent, memory in agent_memories.items()]
        result = await EcommerceGraphRuntime(self.dataset, planner=self.team_planner, is_cancelled=lambda: False).run(job.question, memory_context, workspace_id=workspace_id, run_id=job.run_id, agent_memories=agent_memories)
        status = result.get("status", "failed")
        await self.repository.set_agent_job_status(job.id, status)
        await self.repository.append_agent_event(job.id, "completed" if status == "completed" else status, result.get("analysis") or {})
        if status == "completed" and result.get("analysis"):
            for agent, deliverable in result["analysis"].get("team_deliverables", {}).items():
                await self.repository.upsert_agent_memory(workspace_id, agent, "last_deliverable", deliverable, "agent_run")
        return result
