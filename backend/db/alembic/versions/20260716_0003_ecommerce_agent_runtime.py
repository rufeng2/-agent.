"""Add durable ecommerce agent runtime tables."""
from alembic import op
import sqlalchemy as sa

revision = "20260716_0003"
down_revision = "20260715_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_sessions_user_id", "agent_sessions", ["user_id"])
    op.create_table(
        "agent_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_messages_session_id", "agent_messages", ["session_id"])
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("agent_sessions.id"), nullable=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("execution_mode", sa.String(64), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("fallback_reason", sa.String(128), nullable=False),
        sa.Column("total_latency_ms", sa.Float(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_runs_session_id", "agent_runs", ["session_id"])
    op.create_index("ix_agent_runs_user_id", "agent_runs", ["user_id"])
    op.create_index("ix_agent_runs_execution_mode", "agent_runs", ["execution_mode"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])
    op.create_index("ix_agent_runs_created_at", "agent_runs", ["created_at"])
    op.create_table(
        "tool_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_name", sa.String(128), nullable=False),
        sa.Column("input_data", sa.JSON(), nullable=False),
        sa.Column("output_summary", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tool_executions_run_id", "tool_executions", ["run_id"])
    op.create_index("ix_tool_executions_tool_name", "tool_executions", ["tool_name"])
    op.create_table(
        "ecommerce_recommendations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("agent_runs.id"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("action_type", sa.String(128), nullable=False),
        sa.Column("risk_level", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("expected_impact", sa.Text(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("operator", sa.String(128), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ecommerce_recommendations_run_id", "ecommerce_recommendations", ["run_id"])
    op.create_index("ix_ecommerce_recommendations_risk_level", "ecommerce_recommendations", ["risk_level"])
    op.create_index("ix_ecommerce_recommendations_status", "ecommerce_recommendations", ["status"])
    op.create_table(
        "approval_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("recommendation_id", sa.String(36), sa.ForeignKey("ecommerce_recommendations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(32), nullable=False),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("operator", sa.String(128), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_approval_records_recommendation_id", "approval_records", ["recommendation_id"])
    op.create_index("ix_approval_records_idempotency_key", "approval_records", ["idempotency_key"], unique=True)
    op.create_table(
        "ecommerce_evaluation_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "ecommerce_simulation_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("current_date", sa.Date(), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("seed", sa.Integer(), nullable=False, server_default="20260716"),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "ecommerce_agent_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("workspace_id", sa.String(128), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False, unique=True),
        sa.Column("cancelled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ecommerce_agent_jobs_workspace_id", "ecommerce_agent_jobs", ["workspace_id"])
    op.create_table(
        "ecommerce_agent_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("ecommerce_agent_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ecommerce_agent_events_job_id", "ecommerce_agent_events", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_ecommerce_agent_events_job_id", table_name="ecommerce_agent_events")
    op.drop_table("ecommerce_agent_events")
    op.drop_index("ix_ecommerce_agent_jobs_workspace_id", table_name="ecommerce_agent_jobs")
    op.drop_table("ecommerce_agent_jobs")
    op.drop_table("ecommerce_simulation_state")
    op.drop_table("ecommerce_evaluation_runs")
    op.drop_index("ix_approval_records_idempotency_key", table_name="approval_records")
    op.drop_index("ix_approval_records_recommendation_id", table_name="approval_records")
    op.drop_table("approval_records")
    op.drop_index("ix_ecommerce_recommendations_status", table_name="ecommerce_recommendations")
    op.drop_index("ix_ecommerce_recommendations_risk_level", table_name="ecommerce_recommendations")
    op.drop_index("ix_ecommerce_recommendations_run_id", table_name="ecommerce_recommendations")
    op.drop_table("ecommerce_recommendations")
    op.drop_index("ix_tool_executions_tool_name", table_name="tool_executions")
    op.drop_index("ix_tool_executions_run_id", table_name="tool_executions")
    op.drop_table("tool_executions")
    op.drop_index("ix_agent_runs_created_at", table_name="agent_runs")
    op.drop_index("ix_agent_runs_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_execution_mode", table_name="agent_runs")
    op.drop_index("ix_agent_runs_user_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_session_id", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index("ix_agent_messages_session_id", table_name="agent_messages")
    op.drop_table("agent_messages")
    op.drop_index("ix_agent_sessions_user_id", table_name="agent_sessions")
    op.drop_table("agent_sessions")
