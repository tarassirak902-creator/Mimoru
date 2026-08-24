"""join requests and invite campaign analytics

Revision ID: 0015_join_requests_and_invites
Revises: 0014_night_mode
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_join_requests_and_invites"
down_revision = "0014_night_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("group_settings", sa.Column("join_requests_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("group_settings", sa.Column("join_requests_auto_approve", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "invite_campaigns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("invite_link", sa.String(length=255), nullable=False),
        sa.Column("creates_join_request", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("joined_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requested_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("group_id", "name"),
        sa.UniqueConstraint("invite_link"),
    )
    op.create_index("ix_invite_campaigns_group_id", "invite_campaigns", ["group_id"])
    op.create_index("ix_invite_campaigns_invite_link", "invite_campaigns", ["invite_link"])
    op.create_index("ix_invite_campaigns_active", "invite_campaigns", ["active"])
    op.create_table(
        "join_request_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("invite_campaigns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("user_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_telegram_id", sa.BigInteger(), nullable=True),
        sa.UniqueConstraint("group_id", "user_telegram_id", "requested_at"),
    )
    op.create_index("ix_join_request_records_group_id", "join_request_records", ["group_id"])
    op.create_index("ix_join_request_records_campaign_id", "join_request_records", ["campaign_id"])
    op.create_index("ix_join_request_records_user_telegram_id", "join_request_records", ["user_telegram_id"])
    op.create_index("ix_join_request_records_status", "join_request_records", ["status"])
    op.create_index("ix_join_request_records_requested_at", "join_request_records", ["requested_at"])


def downgrade() -> None:
    op.drop_table("join_request_records")
    op.drop_table("invite_campaigns")
    op.drop_column("group_settings", "join_requests_auto_approve")
    op.drop_column("group_settings", "join_requests_enabled")
