from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.ecommerce.persistence.database import EcommerceDatabase
from backend.ecommerce.persistence.models import (
    AgentMessageModel,
    AgentRunModel,
    AgentSessionModel,
    ApprovalRecordModel,
    RecommendationModel,
    ToolExecutionModel,
    EvaluationRunModel,
    SimulationStateModel,
    AgentJobModel, AgentEventModel,
)


class VersionConflict(ValueError):
    pass


class EcommerceRepository:
    def __init__(self, url: str):
        self.database = EcommerceDatabase(url)

    async def initialize(self) -> None:
        await self.database.initialize()

    async def dispose(self) -> None:
        await self.database.dispose()

    async def create_session(self, user_id: str, title: str) -> AgentSessionModel:
        async with self.database.sessions() as session:
            item = AgentSessionModel(user_id=user_id, title=title)
            session.add(item)
            await session.commit()
            return item

    async def append_message(self, session_id: str, role: str, content: str) -> AgentMessageModel:
        async with self.database.sessions() as session:
            item = AgentMessageModel(session_id=session_id, role=role, content=content)
            session.add(item)
            await session.commit()
            return item

    async def get_session(self, session_id: str) -> AgentSessionModel | None:
        async with self.database.sessions() as session:
            statement = select(AgentSessionModel).options(selectinload(AgentSessionModel.messages)).where(AgentSessionModel.id == session_id)
            return (await session.execute(statement)).scalar_one_or_none()

    async def list_sessions(self, user_id: str) -> list[AgentSessionModel]:
        async with self.database.sessions() as session:
            statement = select(AgentSessionModel).where(AgentSessionModel.user_id == user_id).order_by(AgentSessionModel.updated_at.desc())
            return list((await session.execute(statement)).scalars())

    async def create_recommendation(self, title: str, action_type: str, risk_level: str, reason: str, expected_impact: str, evidence: list, run_id: str | None = None) -> RecommendationModel:
        async with self.database.sessions() as session:
            item = RecommendationModel(run_id=run_id, title=title, action_type=action_type, risk_level=risk_level, reason=reason, expected_impact=expected_impact, evidence=evidence)
            session.add(item)
            await session.commit()
            return item

    async def transition_recommendation(self, recommendation_id: str, target: str, expected_version: int, operator: str, comment: str, idempotency_key: str) -> RecommendationModel:
        async with self.database.sessions() as session:
            duplicate = (await session.execute(select(ApprovalRecordModel).where(ApprovalRecordModel.idempotency_key == idempotency_key))).scalar_one_or_none()
            if duplicate:
                return await session.get(RecommendationModel, duplicate.recommendation_id)  # type: ignore[return-value]
            item = await session.get(RecommendationModel, recommendation_id)
            if item is None:
                raise KeyError(recommendation_id)
            if item.version != expected_version or item.status != "pending":
                raise VersionConflict(f"Expected version {expected_version}, found {item.version}")
            previous = item.status
            item.status = target
            item.version += 1
            item.operator = operator
            session.add(ApprovalRecordModel(
                recommendation_id=item.id, from_status=previous, to_status=target,
                operator=operator, comment=comment, idempotency_key=idempotency_key,
            ))
            await session.commit()
            return item

    async def list_approvals(self, recommendation_id: str) -> list[ApprovalRecordModel]:
        async with self.database.sessions() as session:
            statement = select(ApprovalRecordModel).where(ApprovalRecordModel.recommendation_id == recommendation_id).order_by(ApprovalRecordModel.created_at)
            return list((await session.execute(statement)).scalars())

    async def get_recommendation(self, recommendation_id: str) -> RecommendationModel | None:
        async with self.database.sessions() as session:
            return await session.get(RecommendationModel, recommendation_id)

    async def list_recommendations(self, status: str = "") -> list[RecommendationModel]:
        async with self.database.sessions() as session:
            statement = select(RecommendationModel)
            if status:
                statement = statement.where(RecommendationModel.status == status)
            statement = statement.order_by(RecommendationModel.updated_at.desc())
            return list((await session.execute(statement)).scalars())

    async def create_run(self, run_id: str, session_id: str | None, user_id: str, execution_mode: str, model: str, status: str, fallback_reason: str, total_latency_ms: float, prompt_tokens: int = 0, completion_tokens: int = 0, error: str = "") -> AgentRunModel:
        async with self.database.sessions() as session:
            item = AgentRunModel(
                id=run_id, session_id=session_id, user_id=user_id, execution_mode=execution_mode,
                model=model, status=status, fallback_reason=fallback_reason,
                total_latency_ms=total_latency_ms, prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens, error=error,
            )
            session.add(item)
            await session.commit()
            return item

    async def add_tool_execution(self, run_id: str, tool_name: str, input_data: dict, output_summary: str, latency_ms: float = 0, status: str = "completed") -> ToolExecutionModel:
        async with self.database.sessions() as session:
            item = ToolExecutionModel(run_id=run_id, tool_name=tool_name, input_data=input_data, output_summary=output_summary, latency_ms=latency_ms, status=status)
            session.add(item)
            await session.commit()
            return item

    async def list_runs(self, execution_mode: str = "", status: str = "") -> list[AgentRunModel]:
        async with self.database.sessions() as session:
            statement = select(AgentRunModel)
            if execution_mode:
                statement = statement.where(AgentRunModel.execution_mode == execution_mode)
            if status:
                statement = statement.where(AgentRunModel.status == status)
            statement = statement.order_by(AgentRunModel.created_at.desc())
            return list((await session.execute(statement)).scalars())

    async def get_run(self, run_id: str) -> AgentRunModel | None:
        async with self.database.sessions() as session:
            return await session.get(AgentRunModel, run_id)

    async def list_tool_executions(self, run_id: str) -> list[ToolExecutionModel]:
        async with self.database.sessions() as session:
            statement = select(ToolExecutionModel).where(ToolExecutionModel.run_id == run_id).order_by(ToolExecutionModel.created_at)
            return list((await session.execute(statement)).scalars())

    async def create_evaluation_run(self, mode: str, metrics: dict) -> EvaluationRunModel:
        async with self.database.sessions() as session:
            item = EvaluationRunModel(mode=mode, metrics=metrics)
            session.add(item)
            await session.commit()
            return item

    async def list_evaluation_runs(self) -> list[EvaluationRunModel]:
        async with self.database.sessions() as session:
            statement = select(EvaluationRunModel).order_by(EvaluationRunModel.created_at.desc())
            return list((await session.execute(statement)).scalars())

    async def get_simulation_state(self, baseline_date) -> SimulationStateModel:
        async with self.database.sessions() as session:
            item = await session.get(SimulationStateModel, 1)
            if item is None:
                item = SimulationStateModel(id=1, current_date=baseline_date, step=0, seed=20260716, events=[], version=1)
                session.add(item)
                await session.commit()
            return item

    async def advance_simulation(self, events: list[str], expected_version: int) -> SimulationStateModel:
        async with self.database.sessions() as session:
            item = await session.get(SimulationStateModel, 1)
            if item is None:
                raise KeyError("simulation state")
            if item.version != expected_version:
                raise VersionConflict(f"Expected version {expected_version}, found {item.version}")
            from datetime import timedelta
            item.step += 1
            item.current_date += timedelta(days=1)
            item.events = events
            item.version += 1
            await session.commit()
            return item

    async def reset_simulation(self, baseline_date, expected_version: int) -> SimulationStateModel:
        async with self.database.sessions() as session:
            item = await session.get(SimulationStateModel, 1)
            if item is None:
                raise KeyError("simulation state")
            if item.version != expected_version:
                raise VersionConflict(f"Expected version {expected_version}, found {item.version}")
            item.current_date = baseline_date
            item.step = 0
            item.events = []
            item.version += 1
            await session.commit()
            return item

    async def create_agent_job(self, run_id: str, workspace_id: str, session_id: str, idempotency_key: str, question: str = "") -> AgentJobModel:
        async with self.database.sessions() as session:
            existing = (await session.execute(select(AgentJobModel).where(AgentJobModel.idempotency_key == idempotency_key))).scalar_one_or_none()
            if existing:
                return existing
            item = AgentJobModel(run_id=run_id, workspace_id=workspace_id, session_id=session_id, idempotency_key=idempotency_key, question=question)
            session.add(item)
            await session.commit()
            return item

    async def get_agent_job(self, job_id: str, workspace_id: str) -> AgentJobModel | None:
        async with self.database.sessions() as session:
            return (await session.execute(select(AgentJobModel).where(AgentJobModel.id == job_id, AgentJobModel.workspace_id == workspace_id))).scalar_one_or_none()

    async def cancel_agent_job(self, job_id: str, workspace_id: str) -> AgentJobModel | None:
        async with self.database.sessions() as session:
            item = (await session.execute(select(AgentJobModel).where(AgentJobModel.id == job_id, AgentJobModel.workspace_id == workspace_id))).scalar_one_or_none()
            if item:
                item.cancelled = True
                item.status = "cancelled"
                await session.commit()
            return item

    async def set_agent_job_status(self, job_id: str, status: str) -> AgentJobModel | None:
        async with self.database.sessions() as session:
            item = await session.get(AgentJobModel, job_id)
            if item:
                item.status = status
                await session.commit()
            return item

    async def append_agent_event(self, job_id: str, event_type: str, payload: dict) -> AgentEventModel:
        async with self.database.sessions() as session:
            last = (await session.execute(select(AgentEventModel).where(AgentEventModel.job_id == job_id).order_by(AgentEventModel.sequence.desc()))).scalars().first()
            item = AgentEventModel(job_id=job_id, sequence=(last.sequence + 1 if last else 1), event_type=event_type, payload=payload)
            session.add(item)
            await session.commit()
            return item

    async def list_agent_events(self, job_id: str, after_sequence: int = 0) -> list[AgentEventModel]:
        async with self.database.sessions() as session:
            statement = select(AgentEventModel).where(AgentEventModel.job_id == job_id, AgentEventModel.sequence > after_sequence).order_by(AgentEventModel.sequence)
            return list((await session.execute(statement)).scalars())
