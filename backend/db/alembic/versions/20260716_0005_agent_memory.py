"""Add isolated specialist memories."""
from alembic import op
import sqlalchemy as sa

revision = "20260716_0005"
down_revision = "20260716_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("ecommerce_agent_memories", sa.Column("workspace_id", sa.String(128), primary_key=True), sa.Column("agent", sa.String(64), primary_key=True), sa.Column("memory_key", sa.String(128), primary_key=True), sa.Column("value", sa.JSON(), nullable=False), sa.Column("source", sa.String(64), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))


def downgrade() -> None:
    op.drop_table("ecommerce_agent_memories")
