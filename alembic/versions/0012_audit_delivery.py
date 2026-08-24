"""audit delivery

Revision ID: 0012_audit_delivery
Revises: 0011_timezones_and_recurring
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_audit_delivery"
down_revision = "0011_timezones_and_recurring"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("group_settings", sa.Column("audit_chat_id", sa.BigInteger(), nullable=True))
    op.add_column("group_settings", sa.Column("audit_topic_id", sa.Integer(), nullable=True))
    op.add_column("moderation_logs", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("moderation_logs", sa.Column("delivery_error", sa.Text(), nullable=True))
    op.add_column("moderation_logs", sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_moderation_logs_delivery", "moderation_logs", ["delivered_at", "delivery_attempts"], unique=False)

def downgrade() -> None:
    op.drop_index("ix_moderation_logs_delivery", table_name="moderation_logs")
    op.drop_column("moderation_logs", "delivery_attempts")
    op.drop_column("moderation_logs", "delivery_error")
    op.drop_column("moderation_logs", "delivered_at")
    op.drop_column("group_settings", "audit_topic_id")
    op.drop_column("group_settings", "audit_chat_id")
