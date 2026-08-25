"""moderation command modes

Revision ID: 0045_moderation_command_modes
Revises: 56b9b87f0e44
"""
from alembic import op
import sqlalchemy as sa

revision = "0045_moderation_command_modes"
down_revision = "56b9b87f0e44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "moderation_command_preferences",
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("mode", sa.String(length=16), nullable=False, server_default="both"),
    )


def downgrade() -> None:
    op.drop_table("moderation_command_preferences")
