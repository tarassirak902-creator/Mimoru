"""rank access mode

Revision ID: 0036_rank_access_mode
Revises: 0035_fun_group_settings
"""
from alembic import op
import sqlalchemy as sa

revision = "0036_rank_access_mode"
down_revision = "0035_fun_group_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rank_assignments",
        sa.Column("access_mode", sa.String(length=16), nullable=False, server_default="bot_only"),
    )
    op.create_index("ix_rank_assignments_access_mode", "rank_assignments", ["access_mode"])
    op.execute(
        "UPDATE rank_assignments SET access_mode = 'telegram' "
        "WHERE telegram_admin_managed = true AND rank_code IN "
        "('deputy_owner','chief_admin','chat_admin','voice_admin')"
    )


def downgrade() -> None:
    op.drop_index("ix_rank_assignments_access_mode", table_name="rank_assignments")
    op.drop_column("rank_assignments", "access_mode")
