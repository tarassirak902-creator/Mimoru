"""initial schema"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("users", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("telegram_id", sa.BigInteger(), nullable=False), sa.Column("username", sa.String(64)), sa.Column("first_name", sa.String(128), nullable=False), sa.Column("last_name", sa.String(128)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.UniqueConstraint("telegram_id"))
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])
    op.create_table("groups", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False), sa.Column("title", sa.String(255), nullable=False), sa.Column("owner_telegram_id", sa.BigInteger()), sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.UniqueConstraint("telegram_chat_id"))
    op.create_index("ix_groups_telegram_chat_id", "groups", ["telegram_chat_id"])
    op.create_table("group_settings", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), unique=True), sa.Column("antiflood_enabled", sa.Boolean(), nullable=False), sa.Column("links_enabled", sa.Boolean(), nullable=False), sa.Column("captcha_enabled", sa.Boolean(), nullable=False), sa.Column("welcome_enabled", sa.Boolean(), nullable=False), sa.Column("welcome_text", sa.Text(), nullable=False), sa.Column("warnings_limit", sa.Integer(), nullable=False), sa.Column("default_mute_seconds", sa.Integer(), nullable=False))
    for name, extra in [("warnings", [sa.Column("reason", sa.Text(), nullable=False), sa.Column("active", sa.Boolean(), nullable=False)]), ("punishments", [sa.Column("kind", sa.String(32), nullable=False), sa.Column("reason", sa.Text(), nullable=False), sa.Column("ends_at", sa.DateTime(timezone=True)), sa.Column("active", sa.Boolean(), nullable=False)])]:
        op.create_table(name, sa.Column("id", sa.Integer(), primary_key=True), sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False), sa.Column("user_telegram_id", sa.BigInteger(), nullable=False), sa.Column("moderator_telegram_id", sa.BigInteger(), nullable=False), *extra, sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("forbidden_words", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False), sa.Column("word", sa.String(255), nullable=False), sa.UniqueConstraint("group_id", "word"))
    op.create_table("required_channels", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False), sa.Column("channel_username", sa.String(64), nullable=False), sa.Column("active", sa.Boolean(), nullable=False), sa.UniqueConstraint("group_id", "channel_username"))


def downgrade():
    for table in ["required_channels", "forbidden_words", "punishments", "warnings", "group_settings", "groups", "users"]:
        op.drop_table(table)
