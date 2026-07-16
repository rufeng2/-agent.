import pytest

from backend.ecommerce.persistence.repository import EcommerceRepository
from backend.ecommerce.runtime.service import EcommerceJobService


@pytest.mark.asyncio
async def test_job_events_are_persisted_and_replayed_in_order(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'jobs.db'}")
    await repository.initialize()
    job = await repository.create_agent_job("run-1", "workspace-1", "session-1", "idem-1")
    await repository.append_agent_event(job.id, "planning_started", {"step": 1})
    await repository.append_agent_event(job.id, "tool_completed", {"tool": "kpi"})

    events = await repository.list_agent_events(job.id, after_sequence=0)
    assert [item.sequence for item in events] == [1, 2]
    assert [item.event_type for item in events] == ["planning_started", "tool_completed"]
    await repository.dispose()


@pytest.mark.asyncio
async def test_cancelled_inline_job_does_not_persist_recommendation_result(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'jobs.db'}")
    await repository.initialize()
    service = EcommerceJobService(repository, dataset=None)
    job = await service.create_job("分析经营情况", "workspace-1", "session-1", "idem-2")
    await service.cancel(job.id, "workspace-1")
    result = await service.run_inline(job.id)

    assert result["status"] == "cancelled"
    stored = await repository.get_agent_job(job.id, "workspace-1")
    assert stored.status == "cancelled"
    assert not await repository.list_recommendations()
    await repository.dispose()
