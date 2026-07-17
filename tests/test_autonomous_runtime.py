import pytest

from backend.ecommerce.autonomous_runtime import (
    AutonomousOperationsRuntime,
    DynamicOperationsPlanner,
    GoalContractParser,
)
from backend.ecommerce.data_loader import EcommerceDataLoader
from backend.ecommerce.persistence.repository import EcommerceRepository


def test_goal_parser_requests_kpi_horizon_and_budget():
    result = GoalContractParser(EcommerceDataLoader().load_cached()).parse("提升便携榨汁杯销量")

    assert result.contract is None
    assert set(result.missing_fields) == {"target", "horizon_days", "budget_limit"}
    assert len(result.questions) == 3


def test_dynamic_planner_builds_dependency_dag_for_growth_goal():
    parsed = GoalContractParser(EcommerceDataLoader().load_cached()).parse(
        "未来7天将便携榨汁杯转化率提升15%，预算1000元"
    )
    plan = DynamicOperationsPlanner().build(parsed.contract)

    assert parsed.contract.product_id == "P003"
    assert [step.id for step in plan.steps] == [
        "baseline", "competitors", "content", "experiment", "evaluate"
    ]
    assert plan.steps[2].depends_on == ["baseline", "competitors"]
    assert plan.steps[-1].depends_on == ["experiment"]


@pytest.mark.asyncio
async def test_runtime_replans_until_kpi_is_reached_and_writes_memory(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    dataset = EcommerceDataLoader().load_cached()
    parsed = GoalContractParser(dataset).parse("未来7天将便携榨汁杯转化率提升15%，预算1000元")
    calls = []

    async def tool_runner(step, state):
        calls.append((state["iteration"], step.id))
        if step.id == "evaluate":
            return {"metric": "conversion_rate", "baseline": 2.0, "current": 2.1 if state["iteration"] == 1 else 2.35, "cost": 0}
        return {"status": "completed", "cost": 50 if step.id == "experiment" else 0, "evidence": [{"source": "sandbox"}]}

    runtime = AutonomousOperationsRuntime(repository, dataset, tool_runner=tool_runner)
    result = await runtime.run(parsed.contract, "workspace-1", "alice")

    assert result.status == "succeeded"
    assert result.iteration == 2
    assert result.evaluation["achieved"] is True
    assert result.reflections[0]["decision"] == "replan"
    assert result.trace[0]["event"] == "run_started"
    assert {item["event"] for item in result.trace} >= {"step_started", "step_completed", "reflection", "run_succeeded"}
    assert result.trace_stats["steps"] == 10
    memories = await repository.list_agent_memories("workspace-1")
    assert {item.agent for item in memories} >= {"episodic", "procedural"}
    await repository.dispose()


@pytest.mark.asyncio
async def test_runtime_stops_when_budget_would_be_exceeded(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    dataset = EcommerceDataLoader().load_cached()
    contract = GoalContractParser(dataset).parse("未来7天将便携榨汁杯转化率提升15%，预算100元").contract

    async def expensive_runner(step, _state):
        return {"status": "completed", "cost": 120, "evidence": [{"source": "sandbox"}]}

    result = await AutonomousOperationsRuntime(repository, dataset, tool_runner=expensive_runner).run(contract, "workspace-1", "alice")

    assert result.status == "stopped"
    assert result.stop_reason == "budget_limit_exceeded"
    await repository.dispose()


@pytest.mark.asyncio
async def test_later_run_recalls_only_successful_procedural_memory(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    dataset = EcommerceDataLoader().load_cached()
    contract = GoalContractParser(dataset).parse("未来7天将便携榨汁杯转化率提升15%，预算1000元").contract
    runtime = AutonomousOperationsRuntime(repository, dataset)
    first = await runtime.run(contract, "workspace-1", "alice")
    second = await runtime.run(contract, "workspace-1", "alice")

    assert first.status == "succeeded"
    assert second.plan.version > first.plan.version
    assert second.memories_used == ["conversion_rate:P003"]
    await repository.dispose()


@pytest.mark.asyncio
async def test_failed_tool_run_can_resume_on_the_same_task(tmp_path):
    repository = EcommerceRepository(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    await repository.initialize()
    dataset = EcommerceDataLoader().load_cached()
    contract = GoalContractParser(dataset).parse("未来7天将便携榨汁杯转化率提升15%，预算1000元").contract
    failed_once = False

    async def flaky_runner(step, state):
        nonlocal failed_once
        if step.id == "experiment" and not failed_once:
            failed_once = True
            raise RuntimeError("sandbox worker interrupted")
        if step.id == "evaluate":
            return {"metric": "conversion_rate", "baseline": 2, "current": 2.4, "cost": 0}
        return {"status": "completed", "cost": 0, "evidence": [{"source": "sandbox"}]}

    runtime = AutonomousOperationsRuntime(repository, dataset, tool_runner=flaky_runner)
    failed = await runtime.run(contract, "workspace-1", "alice")
    resumed = await runtime.resume(failed.task_id, "workspace-1", "alice")

    assert failed.status == "failed"
    assert failed.stop_reason == "tool_error:experiment"
    assert resumed.status == "succeeded"
    assert resumed.task_id == failed.task_id
    await repository.dispose()
