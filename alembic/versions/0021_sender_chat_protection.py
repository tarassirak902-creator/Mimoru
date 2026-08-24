"""sender chat protection

Revision ID: 0021_sender_chat_protection
Revises: 0020_mention_protection
"""
from alembic import op
import sqlalchemy as sa

revision = "0021_sender_chat_protection"
down_revision = "0020_mention_protection"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("group_settings", sa.Column("sender_chat_filter_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("group_settings", sa.Column("allow_group_sender_identity", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table(
        "allowed_sender_chats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(255)),
        sa.Column("username", sa.String(64)),
        sa.Column("added_by_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("group_id", "sender_chat_id"),
    )
    op.create_index("ix_allowed_sender_chats_group_id", "allowed_sender_chats", ["group_id"])
    op.create_index("ix_allowed_sender_chats_sender_chat_id", "allowed_sender_chats", ["sender_chat_id"])

def downgrade() -> None:
    op.drop_index("ix_allowed_sender_chats_sender_chat_id", table_name="allowed_sender_chats")
    op.drop_index("ix_allowed_sender_chats_group_id", table_name="allowed_sender_chats")
    op.drop_table("allowed_sender_chats")
    op.drop_column("group_settings", "allow_group_sender_identity")
    op.drop_column("group_settings", "sender_chat_filter_enabled")
