"""Add durable ecommerce agent runtime tables."""
from alembic import op
import sqlalchemy as sa

revision = "20260716_0003"
down_revision = "20260715_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
