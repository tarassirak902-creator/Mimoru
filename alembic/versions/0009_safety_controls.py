"""trusted users, anti-raid and warning expiry

Revision ID: 0009_safety_controls
Revises: 0008_hardening
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_safety_controls"
down_revision = "0008_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("group_settings", sa.Column("anti_raid_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("group_settings", sa.Column("anti_raid_limit", sa.Integer(), nullable=False, server_default="10"))
    op.add_column("group_settings", sa.Column("anti_raid_window_seconds", sa.Integer(), nullable=False, server_default="60"))
    op.add_column("group_settings", sa.Column("warning_expire_days", sa.Integer(), nullable=False, server_default="30"))
    op.create_table(
        "trusted_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("added_by_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("group_id", "user_telegram_id", name="uq_trusted_users_group_user"),
    )
    op.create_index("ix_trusted_users_group_id", "trusted_users", ["group_id"])
    op.create_index("ix_trusted_users_user_telegram_id", "trusted_users", ["user_telegram_id"])


def downgrade() -> None:
    op.drop_index("ix_trusted_users_user_telegram_id", table_name="trusted_users")
    op.drop_index("ix_trusted_users_group_id", table_name="trusted_users")
    op.drop_table("trusted_users")
    op.drop_column("group_settings", "warning_expire_days")
    op.drop_column("group_settings", "anti_raid_window_seconds")
    op.drop_column("group_settings", "anti_raid_limit")
    op.drop_column("group_settings", "anti_raid_enabled")
