"""newcomer quarantine

Revision ID: 0016_newcomer_quarantine
Revises: 0015_join_requests_and_invites
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_newcomer_quarantine"
down_revision = "0015_join_requests_and_invites"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("group_settings", sa.Column("newcomer_quarantine_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("group_settings", sa.Column("newcomer_quarantine_seconds", sa.Integer(), nullable=False, server_default="86400"))
    op.add_column("group_settings", sa.Column("newcomer_quarantine_block_links", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("group_settings", sa.Column("newcomer_quarantine_block_media", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("group_settings", sa.Column("newcomer_quarantine_block_forwards", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table(
        "new_member_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="join"),
        sa.UniqueConstraint("group_id", "user_telegram_id"),
    )
    op.create_index("ix_new_member_records_group_id", "new_member_records", ["group_id"])
    op.create_index("ix_new_member_records_user_telegram_id", "new_member_records", ["user_telegram_id"])
    op.create_index("ix_new_member_records_joined_at", "new_member_records", ["joined_at"])


def downgrade() -> None:
    op.drop_table("new_member_records")
    op.drop_column("group_settings", "newcomer_quarantine_block_forwards")
    op.drop_column("group_settings", "newcomer_quarantine_block_media")
    op.drop_column("group_settings", "newcomer_quarantine_block_links")
    op.drop_column("group_settings", "newcomer_quarantine_seconds")
    op.drop_column("group_settings", "newcomer_quarantine_enabled")
