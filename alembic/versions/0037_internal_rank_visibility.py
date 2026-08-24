"""internal-only rank visibility

Revision ID: 0037_internal_rank_visibility
Revises: 0036_rank_access_mode
"""
from alembic import op

revision = "0037_internal_rank_visibility"
down_revision = "0036_rank_access_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE rank_assignments SET access_mode = 'bot_only', telegram_admin_managed = false "
        "WHERE rank_code IN ('voice_admin','helper','untouchable')"
    )


def downgrade() -> None:
    pass
