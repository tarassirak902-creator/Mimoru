"""application slow mode

Revision ID: 0017_application_slow_mode
Revises: 0016_newcomer_quarantine
"""
from alembic import op
import sqlalchemy as sa

revision = "0017_application_slow_mode"
down_revision = "0016_newcomer_quarantine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "group_settings",
        sa.Column("slow_mode_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "group_settings",
        sa.Column("slow_mode_seconds", sa.Integer(), nullable=False, server_default="10"),
    )


def downgrade() -> None:
    op.drop_column("group_settings", "slow_mode_seconds")
    op.drop_column("group_settings", "slow_mode_enabled")
