"""lockdown, moderator notes and scheduled messages

Revision ID: 0010_operations_plus
Revises: 0009_safety_controls
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_operations_plus"
down_revision = "0009_safety_controls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("group_settings", sa.Column("lockdown_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("group_settings", sa.Column("lockdown_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("group_settings", sa.Column("lockdown_previous_permissions", sa.JSON(), nullable=True))
    op.create_table(
        "moderator_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("author_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_moderator_notes_group_id", "moderator_notes", ["group_id"])
    op.create_index("ix_moderator_notes_target", "moderator_notes", ["target_telegram_id"])
    op.create_index("ix_moderator_notes_created", "moderator_notes", ["created_at"])
    op.create_table(
        "scheduled_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("creator_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("send_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("sent_message_id", sa.BigInteger(), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_scheduled_messages_group_id", "scheduled_messages", ["group_id"])
    op.create_index("ix_scheduled_messages_send_at", "scheduled_messages", ["send_at"])
    op.create_index("ix_scheduled_messages_status", "scheduled_messages", ["status"])


def downgrade() -> None:
    op.drop_table("scheduled_messages")
    op.drop_table("moderator_notes")
    op.drop_column("group_settings", "lockdown_previous_permissions")
    op.drop_column("group_settings", "lockdown_until")
    op.drop_column("group_settings", "lockdown_enabled")
