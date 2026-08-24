"""durable chat permission transitions

Revision ID: 0041_chat_permission_transitions
Revises: 0040_rank_provisioning_intents
"""
from alembic import op
import sqlalchemy as sa

revision = "0041_chat_permission_transitions"
down_revision = "0040_rank_provisioning_intents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_permission_transitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("operation", sa.String(length=24), nullable=False),
        sa.Column("previous_permissions", sa.JSON(), nullable=True),
        sa.Column("desired_permissions", sa.JSON(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("group_id", name="uq_chat_permission_transition_group"),
    )
    op.create_index("ix_chat_permission_transitions_group_id", "chat_permission_transitions", ["group_id"])
    op.create_index("ix_chat_permission_transitions_operation", "chat_permission_transitions", ["operation"])
    op.create_index("ix_chat_permission_transitions_created_at", "chat_permission_transitions", ["created_at"])


def downgrade() -> None:
    op.drop_table("chat_permission_transitions")
