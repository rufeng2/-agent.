"""Add persisted marketing campaigns."""
from alembic import op
import sqlalchemy as sa

revision = "20260716_0008"
down_revision = "20260716_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ecommerce_marketing_campaigns",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(128), nullable=False),
        sa.Column("task_id", sa.String(36), nullable=False, unique=True),
        sa.Column("product_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("daily_budget", sa.Float(), nullable=False),
        sa.Column("target_acos_pct", sa.Float(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ecommerce_marketing_campaigns_workspace_id", "ecommerce_marketing_campaigns", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("ecommerce_marketing_campaigns")
