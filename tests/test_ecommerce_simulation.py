from pathlib import Path

import pytest

from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.persistence.repository import EcommerceRepository, VersionConflict
from backend.ecommerce.simulation import SimulationEngine


def _baseline():
    return EcommerceDataLoader(Path("data/ecommerce")).load()


def test_simulation_is_deterministic_and_changes_product_metrics():
    first = SimulationEngine.apply(_baseline(), step=2, seed=20260716)
    second = SimulationEngine.apply(_baseline(), step=2, seed=20260716)

    assert first.state.model_dump() == second.state.model_dump()
    assert first.deltas == second.deltas
    assert first.state.events
    assert any(any(value != 0 for value in delta.values()) for delta in first.deltas.values())


def test_simulated_metrics_remain_in_business_bounds():
    result = SimulationEngine.apply(_baseline(), step=20, seed=20260716)

    assert all(item.stock >= 0 for item in result.dataset.inventory)
    assert all(1 <= item.rating <= 5 for item in result.dataset.reviews)
    assert all(item.gmv >= 0 and item.orders >= 0 for item in result.dataset.orders)
    assert all(item.visitors >= item.add_to_cart >= 0 for item in result.dataset.traffic)


@pytest.mark.asyncio
async def test_simulation_state_survives_restart_and_reset(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}"
    first = EcommerceRepository(url)
    await first.initialize()
    baseline_date = max(row.date for row in _baseline().orders)
    initial = await first.get_simulation_state(baseline_date)
    advanced = await first.advance_simulation(["竞品降价"], expected_version=initial.version)
    await first.dispose()

    second = EcommerceRepository(url)
    await second.initialize()
    restored = await second.get_simulation_state(baseline_date)
    assert restored.step == 1
    assert restored.current_date.isoformat() == "2026-07-16"
    assert restored.events == ["竞品降价"]

    reset = await second.reset_simulation(baseline_date, expected_version=restored.version)
    assert reset.step == 0
    assert reset.current_date == baseline_date
    await second.dispose()


@pytest.mark.asyncio
async def test_simulation_advance_rejects_stale_version(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    baseline_date = max(row.date for row in _baseline().orders)
    state = await repository.get_simulation_state(baseline_date)
    await repository.advance_simulation(["补货到仓"], expected_version=state.version)

    with pytest.raises(VersionConflict):
        await repository.advance_simulation(["大促流量上涨"], expected_version=state.version)
    await repository.dispose()
