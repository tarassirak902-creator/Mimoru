"""scheduled night mode

Revision ID: 0014_night_mode
Revises: 0013_client_management
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_night_mode"
down_revision = "0013_client_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("group_settings", sa.Column("night_mode_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("group_settings", sa.Column("night_mode_start", sa.String(length=5), nullable=False, server_default="23:00"))
    op.add_column("group_settings", sa.Column("night_mode_end", sa.String(length=5), nullable=False, server_default="07:00"))
    op.add_column("group_settings", sa.Column("night_mode_active", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("group_settings", sa.Column("night_mode_previous_permissions", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("group_settings", "night_mode_previous_permissions")
    op.drop_column("group_settings", "night_mode_active")
    op.drop_column("group_settings", "night_mode_end")
    op.drop_column("group_settings", "night_mode_start")
    op.drop_column("group_settings", "night_mode_enabled")
