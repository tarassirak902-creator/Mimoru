"""group marriages

Revision ID: 0032_group_marriages
Revises: 0031_rank_mute_restore
"""
from alembic import op
import sqlalchemy as sa

revision = "0032_group_marriages"
down_revision = "0031_rank_mute_restore"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "group_marriages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user1_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("user2_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("group_id", "user1_telegram_id", "user2_telegram_id", name="uq_group_marriage_pair"),
    )
    op.create_index("ix_group_marriages_group_id", "group_marriages", ["group_id"])
    op.create_index("ix_group_marriages_user1_telegram_id", "group_marriages", ["user1_telegram_id"])
    op.create_index("ix_group_marriages_user2_telegram_id", "group_marriages", ["user2_telegram_id"])
    op.create_index("ix_group_marriages_active", "group_marriages", ["active"])


def downgrade() -> None:
    op.drop_index("ix_group_marriages_active", table_name="group_marriages")
    op.drop_index("ix_group_marriages_user2_telegram_id", table_name="group_marriages")
    op.drop_index("ix_group_marriages_user1_telegram_id", table_name="group_marriages")
    op.drop_index("ix_group_marriages_group_id", table_name="group_marriages")
    op.drop_table("group_marriages")
