"""game auto-immunity preferences

Revision ID: 0034_fun_auto_immunity
Revises: 0033_game_events
"""
from alembic import op
import sqlalchemy as sa

revision = "0034_fun_auto_immunity"
down_revision = "0033_game_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fun_auto_immunity",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("group_id", "user_telegram_id", name="uq_fun_auto_immunity_group_user"),
    )
    op.create_index("ix_fun_auto_immunity_group_id", "fun_auto_immunity", ["group_id"])
    op.create_index("ix_fun_auto_immunity_user_telegram_id", "fun_auto_immunity", ["user_telegram_id"])
    op.create_index("ix_fun_auto_immunity_enabled", "fun_auto_immunity", ["enabled"])


def downgrade() -> None:
    op.drop_index("ix_fun_auto_immunity_enabled", table_name="fun_auto_immunity")
    op.drop_index("ix_fun_auto_immunity_user_telegram_id", table_name="fun_auto_immunity")
    op.drop_index("ix_fun_auto_immunity_group_id", table_name="fun_auto_immunity")
    op.drop_table("fun_auto_immunity")
