"""full feature tables and settings

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

def upgrade():
    fields = [
        ("antiflood_limit", sa.Integer(), "6"), ("antiflood_window_seconds", sa.Integer(), "10"),
        ("antiflood_mute_seconds", sa.Integer(), "1800"), ("repeats_enabled", sa.Boolean(), "true"),
        ("repeats_limit", sa.Integer(), "3"), ("caps_enabled", sa.Boolean(), "false"),
        ("caps_percent", sa.Integer(), "70"), ("caps_min_length", sa.Integer(), "15"),
        ("voices_allowed", sa.Boolean(), "true"), ("stickers_allowed", sa.Boolean(), "true"),
        ("forwards_allowed", sa.Boolean(), "true"),
    ]
    for name, typ, default in fields:
        op.add_column("group_settings", sa.Column(name, typ, nullable=False, server_default=sa.text(default)))
    op.add_column("group_settings", sa.Column("rules_text", sa.Text(), nullable=False, server_default="Правила пока не настроены."))
    op.create_table("auto_responses",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trigger", sa.String(255), nullable=False), sa.Column("response_text", sa.Text(), nullable=False),
        sa.Column("match_type", sa.String(32), nullable=False, server_default="contains"), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_telegram_id", sa.BigInteger(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("group_id", "trigger"))
    op.create_index("ix_auto_responses_group_id", "auto_responses", ["group_id"])
    op.create_table("complaints",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reporter_telegram_id", sa.BigInteger(), nullable=False), sa.Column("target_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False), sa.Column("message_text", sa.Text()), sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_index("ix_complaints_group_id", "complaints", ["group_id"])
    op.create_table("daily_stats",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False), sa.Column("date", sa.String(10), nullable=False),
        sa.Column("messages_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("deleted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("group_id", "user_telegram_id", "date"))
    op.create_index("ix_daily_stats_group_date", "daily_stats", ["group_id", "date"])
    op.create_table("support_tickets",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="SET NULL")), sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="new"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))

def downgrade():
    for table in ["support_tickets", "daily_stats", "complaints", "auto_responses"]:
        op.drop_table(table)
    for name in ["rules_text","forwards_allowed","stickers_allowed","voices_allowed","caps_min_length","caps_percent","caps_enabled","repeats_limit","repeats_enabled","antiflood_mute_seconds","antiflood_window_seconds","antiflood_limit"]:
        op.drop_column("group_settings", name)
