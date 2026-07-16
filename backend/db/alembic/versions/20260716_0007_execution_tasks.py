"""Add LangGraph execution tasks."""
from alembic import op
import sqlalchemy as sa

revision = "20260716_0007"
down_revision = "20260716_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ecommerce_execution_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(128), nullable=False),
        sa.Column("operator", sa.String(128), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ecommerce_execution_tasks_workspace_id", "ecommerce_execution_tasks", ["workspace_id"])
    op.create_index("ix_ecommerce_execution_tasks_status", "ecommerce_execution_tasks", ["status"])


def downgrade() -> None:
    op.drop_table("ecommerce_execution_tasks")
