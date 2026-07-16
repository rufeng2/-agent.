"""Add executable commerce action state."""
from alembic import op
import sqlalchemy as sa

revision = "20260716_0004"
down_revision = "20260716_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("ecommerce_catalog_state", sa.Column("product_id", sa.String(36), primary_key=True), sa.Column("listing_status", sa.String(32), nullable=False, server_default="listed"), sa.Column("price_override", sa.Float(), nullable=True), sa.Column("version", sa.Integer(), nullable=False, server_default="1"), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_ecommerce_catalog_state_listing_status", "ecommerce_catalog_state", ["listing_status"])
    op.create_table("ecommerce_action_executions", sa.Column("id", sa.String(36), primary_key=True), sa.Column("recommendation_id", sa.String(36), sa.ForeignKey("ecommerce_recommendations.id"), nullable=False, unique=True), sa.Column("action_type", sa.String(64), nullable=False), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("receipt", sa.JSON(), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_ecommerce_action_executions_action_type", "ecommerce_action_executions", ["action_type"])


def downgrade() -> None:
    op.drop_table("ecommerce_action_executions")
    op.drop_table("ecommerce_catalog_state")
