"""group-specific moderation reasons

Revision ID: 0024_moderation_reasons
Revises: 0023_ad_order_payments
"""
from alembic import op
import sqlalchemy as sa

revision = "0024_moderation_reasons"
down_revision = "0023_ad_order_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("group_settings", sa.Column("moderation_reasons_initialized", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "moderation_reasons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("actions", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("group_id", "name", name="uq_moderation_reasons_group_name"),
    )
    op.create_index("ix_moderation_reasons_group_id", "moderation_reasons", ["group_id"])
    op.create_index("ix_moderation_reasons_active", "moderation_reasons", ["active"])


def downgrade() -> None:
    op.drop_index("ix_moderation_reasons_active", table_name="moderation_reasons")
    op.drop_index("ix_moderation_reasons_group_id", table_name="moderation_reasons")
    op.drop_table("moderation_reasons")
    op.drop_column("group_settings", "moderation_reasons_initialized")
