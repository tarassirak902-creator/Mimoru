"""durable rank provisioning intents

Revision ID: 0040_rank_provisioning_intents
Revises: 0039_broadcast_delivery_claims
"""
from alembic import op
import sqlalchemy as sa

revision = "0040_rank_provisioning_intents"
down_revision = "0039_broadcast_delivery_claims"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rank_provisioning_intents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("operation", sa.String(length=24), nullable=False),
        sa.Column("telegram_action", sa.String(length=16), nullable=False),
        sa.Column("desired_rank_code", sa.String(length=32), nullable=True),
        sa.Column("desired_access_mode", sa.String(length=16), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("group_id", "user_telegram_id", name="uq_rank_provisioning_group_user"),
    )
    op.create_index("ix_rank_provisioning_intents_group_id", "rank_provisioning_intents", ["group_id"])
    op.create_index("ix_rank_provisioning_intents_user_telegram_id", "rank_provisioning_intents", ["user_telegram_id"])
    op.create_index("ix_rank_provisioning_intents_actor_telegram_id", "rank_provisioning_intents", ["actor_telegram_id"])
    op.create_index("ix_rank_provisioning_intents_operation", "rank_provisioning_intents", ["operation"])
    op.create_index("ix_rank_provisioning_intents_telegram_action", "rank_provisioning_intents", ["telegram_action"])
    op.create_index("ix_rank_provisioning_intents_created_at", "rank_provisioning_intents", ["created_at"])
    op.create_index("ix_rank_provisioning_intents_updated_at", "rank_provisioning_intents", ["updated_at"])


def downgrade() -> None:
    op.drop_table("rank_provisioning_intents")
