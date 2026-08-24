"""group game auto activity settings

Revision ID: 0035_fun_group_settings
Revises: 0034_fun_auto_immunity
"""
from alembic import op
import sqlalchemy as sa

revision = "0035_fun_group_settings"
down_revision = "0034_fun_auto_immunity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fun_group_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("auto_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("interval_code", sa.String(length=16), nullable=False, server_default="15_20"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("group_id", name="uq_fun_group_settings_group"),
    )
    op.create_index("ix_fun_group_settings_group_id", "fun_group_settings", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_fun_group_settings_group_id", table_name="fun_group_settings")
    op.drop_table("fun_group_settings")
