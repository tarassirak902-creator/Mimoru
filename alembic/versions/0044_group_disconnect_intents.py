"""group disconnect intents

Revision ID: 0044_group_disconnect_intents
Revises: 0043_deleted_cleanup_retries
"""
from alembic import op
import sqlalchemy as sa

revision = "0044_group_disconnect_intents"
down_revision = "0043_deleted_cleanup_retries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "group_disconnect_intents",
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_group_disconnect_intents_status", "group_disconnect_intents", ["status"])


def downgrade() -> None:
    op.drop_table("group_disconnect_intents")
