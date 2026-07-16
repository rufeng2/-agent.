"""Add proactive automation rules."""
from alembic import op
import sqlalchemy as sa

revision = "20260716_0006"
down_revision = "20260716_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("ecommerce_automation_rules", sa.Column("id", sa.String(36), primary_key=True), sa.Column("workspace_id", sa.String(128), nullable=False), sa.Column("name", sa.String(128), nullable=False), sa.Column("trigger_type", sa.String(32), nullable=False), sa.Column("interval_minutes", sa.Integer(), nullable=False), sa.Column("task_prompt", sa.Text(), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False), sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True), sa.Column("run_count", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_ecommerce_automation_rules_workspace_id", "ecommerce_automation_rules", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("ecommerce_automation_rules")
