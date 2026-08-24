"""coordinated campaign spam protection

Revision ID: 0018_campaign_spam
Revises: 0017_application_slow_mode
"""
from alembic import op
import sqlalchemy as sa

revision = "0018_campaign_spam"
down_revision = "0017_application_slow_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "group_settings",
        sa.Column("campaign_spam_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "group_settings",
        sa.Column("campaign_spam_limit", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "group_settings",
        sa.Column("campaign_spam_window_seconds", sa.Integer(), nullable=False, server_default="120"),
    )
    op.add_column(
        "group_settings",
        sa.Column("campaign_spam_mute_seconds", sa.Integer(), nullable=False, server_default="3600"),
    )


def downgrade() -> None:
    op.drop_column("group_settings", "campaign_spam_mute_seconds")
    op.drop_column("group_settings", "campaign_spam_window_seconds")
    op.drop_column("group_settings", "campaign_spam_limit")
    op.drop_column("group_settings", "campaign_spam_enabled")
