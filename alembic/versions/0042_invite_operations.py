"""durable invite operations

Revision ID: 0042_invite_operations
Revises: 0041_chat_permission_transitions
"""
from alembic import op
import sqlalchemy as sa

revision = "0042_invite_operations"
down_revision = "0041_chat_permission_transitions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invite_operations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("invite_campaigns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("operation", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=True),
        sa.Column("invite_link", sa.String(length=255), nullable=True),
        sa.Column("creates_join_request", sa.Boolean(), nullable=True),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_invite_operations_group_id", "invite_operations", ["group_id"])
    op.create_index("ix_invite_operations_campaign_id", "invite_operations", ["campaign_id"])
    op.create_index("ix_invite_operations_operation", "invite_operations", ["operation"])
    op.create_index("ix_invite_operations_status", "invite_operations", ["status"])
    op.create_index("ix_invite_operations_invite_link", "invite_operations", ["invite_link"])
    op.create_index("ix_invite_operations_actor_telegram_id", "invite_operations", ["actor_telegram_id"])
    op.create_index("ix_invite_operations_created_at", "invite_operations", ["created_at"])


def downgrade() -> None:
    op.drop_table("invite_operations")
