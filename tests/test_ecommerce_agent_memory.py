from pathlib import Path

import pytest

from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.persistence.repository import EcommerceRepository
from backend.ecommerce.runtime.graph import EcommerceGraphRuntime
from backend.ecommerce.runtime.service import EcommerceJobService


def _dataset():
    return EcommerceDataLoader(Path("data/ecommerce")).load_cached()


@pytest.mark.asyncio
async def test_memories_are_isolated_by_workspace_and_agent(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'memory.db'}")
    await repository.initialize()
    await repository.upsert_agent_memory("shop-a", "pricing", "pricing_policy", {"minimum_margin_pct": 45})
    await repository.upsert_agent_memory("shop-a", "listing", "brand_policy", {"tone": "premium"})
    await repository.upsert_agent_memory("shop-b", "pricing", "pricing_policy", {"minimum_margin_pct": 25})

    pricing = await repository.list_agent_memories("shop-a", "pricing")
    assert len(pricing) == 1
    assert pricing[0].value["minimum_margin_pct"] == 45
    await repository.dispose()


@pytest.mark.asyncio
async def test_pricing_agent_applies_its_memory_policy():
    result = await EcommerceGraphRuntime(_dataset()).run(
        "给主推商品定价", [], agent_memories={"pricing": {"pricing_policy": {"minimum_margin_pct": 55}}}
    )
    pricing = result["analysis"]["team_deliverables"]["pricing"]
    assert pricing["gross_margin_rate"] >= 55
    assert pricing["memory_policy"]["minimum_margin_pct"] == 55


@pytest.mark.asyncio
async def test_job_seeds_and_updates_specialist_memories(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'memory.db'}")
    await repository.initialize()
    service = EcommerceJobService(repository, _dataset())
    job = await service.create_job("帮我选一个商品推荐", "shop-a", "", "memory-job")
    await service.run_inline(job.id, "shop-a")

    memories = await repository.list_agent_memories("shop-a", "product_research")
    assert {item.memory_key for item in memories} == {"selection_policy", "last_deliverable"}
    await repository.dispose()
