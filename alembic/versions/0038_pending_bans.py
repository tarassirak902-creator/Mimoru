"""pending bans for users not currently in a group

Revision ID: 0038_pending_bans
Revises: 0037_internal_rank_visibility
"""
from alembic import op
import sqlalchemy as sa

revision = "0038_pending_bans"
down_revision = "0037_internal_rank_visibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pending_bans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("moderator_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default="Предварительный бан"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("group_id", "user_telegram_id", name="uq_pending_ban_group_user"),
        sa.UniqueConstraint("group_id", "username", name="uq_pending_ban_group_username"),
    )
    op.create_index("ix_pending_bans_group_id", "pending_bans", ["group_id"])
    op.create_index("ix_pending_bans_user_telegram_id", "pending_bans", ["user_telegram_id"])
    op.create_index("ix_pending_bans_username", "pending_bans", ["username"])
    op.create_index("ix_pending_bans_active", "pending_bans", ["active"])


def downgrade() -> None:
    op.drop_table("pending_bans")
