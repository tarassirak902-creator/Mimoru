"""rank mute restoration flag

Revision ID: 0031_rank_mute_restore
Revises: 0030_group_rank_system
"""
from alembic import op
import sqlalchemy as sa

revision = "0031_rank_mute_restore"
down_revision = "0030_group_rank_system"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rank_assignments",
        sa.Column("restore_after_mute", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_rank_assignments_restore_after_mute",
        "rank_assignments",
        ["restore_after_mute"],
    )


def downgrade() -> None:
    op.drop_index("ix_rank_assignments_restore_after_mute", table_name="rank_assignments")
    op.drop_column("rank_assignments", "restore_after_mute")
