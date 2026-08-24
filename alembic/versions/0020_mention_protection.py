"""mass mention and hashtag protection

Revision ID: 0020_mention_protection
Revises: 0019_edit_protection
"""
from alembic import op
import sqlalchemy as sa

revision = "0020_mention_protection"
down_revision = "0019_edit_protection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "group_settings",
        sa.Column("mention_filter_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "group_settings",
        sa.Column("mention_limit", sa.Integer(), nullable=False, server_default="5"),
    )
    op.add_column(
        "group_settings",
        sa.Column("hashtag_limit", sa.Integer(), nullable=False, server_default="10"),
    )
    op.add_column(
        "group_settings",
        sa.Column("mention_mute_seconds", sa.Integer(), nullable=False, server_default="1800"),
    )


def downgrade() -> None:
    op.drop_column("group_settings", "mention_mute_seconds")
    op.drop_column("group_settings", "hashtag_limit")
    op.drop_column("group_settings", "mention_limit")
    op.drop_column("group_settings", "mention_filter_enabled")
