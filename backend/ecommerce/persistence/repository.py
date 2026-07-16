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
