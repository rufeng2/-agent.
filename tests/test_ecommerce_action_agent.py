from pathlib import Path

import pytest

from backend.ecommerce.action_agent import CommerceActionAgent
from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.persistence.repository import EcommerceRepository


def _dataset():
    return EcommerceDataLoader(Path("data/ecommerce")).load_cached()


def test_price_action_rejects_unsafe_price_change():
    agent = CommerceActionAgent(_dataset())
    with pytest.raises(ValueError, match="20%"):
        agent.propose("price_update", "P001", {"new_price": 50})


def test_marketing_action_contains_plan_and_approval_payload():
    proposal = CommerceActionAgent(_dataset()).propose("marketing_plan", "P001", {"goal": "新品冷启动"})
    assert proposal["action_type"] == "marketing_plan"
    assert proposal["payload"]["plan"]["strategy"]
    assert proposal["risk_level"] == "medium"


@pytest.mark.asyncio
async def test_approved_price_action_changes_catalog_and_is_idempotent(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'actions.db'}")
    await repository.initialize()
    agent = CommerceActionAgent(_dataset(), repository)
    recommendation = await repository.create_recommendation("调价", "price_update", "high", "test", "test", [{"action_payload": {"action_type": "price_update", "product_id": "P001", "new_price": 188}}])
    await repository.transition_recommendation(recommendation.id, "approved", 1, "tester", "ok", "approve-price")

    first = await agent.execute(recommendation.id)
    second = await agent.execute(recommendation.id)
    states = await repository.list_catalog_states()

    assert first == second
    assert states[0].price_override == 188
    await repository.dispose()
