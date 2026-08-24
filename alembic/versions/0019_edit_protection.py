"""edited message protection

Revision ID: 0019_edit_protection
Revises: 0018_campaign_spam
"""
from alembic import op
import sqlalchemy as sa

revision = "0019_edit_protection"
down_revision = "0018_campaign_spam"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "group_settings",
        sa.Column("edit_protection_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "group_settings",
        sa.Column("edit_protection_window_seconds", sa.Integer(), nullable=False, server_default="172800"),
    )


def downgrade() -> None:
    op.drop_column("group_settings", "edit_protection_window_seconds")
    op.drop_column("group_settings", "edit_protection_enabled")
