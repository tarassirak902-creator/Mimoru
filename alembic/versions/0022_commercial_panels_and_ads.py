"""commercial panels and ads

Revision ID: 0022_commercial_panels_and_ads
Revises: 0021_sender_chat_protection
"""
from alembic import op
import sqlalchemy as sa

revision = "0022_commercial_panels_and_ads"
down_revision = "0021_sender_chat_protection"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("ad_placements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("price_stars", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("format_text", sa.String(255), nullable=False, server_default="1 публикация на 24 часа"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("group_id", name="uq_ad_placements_group"),
    )
    op.create_index("ix_ad_placements_group_id", "ad_placements", ["group_id"])
    op.create_index("ix_ad_placements_owner_telegram_id", "ad_placements", ["owner_telegram_id"])
    op.create_index("ix_ad_placements_active", "ad_placements", ["active"])
    op.create_table("ad_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("placement_id", sa.Integer(), sa.ForeignKey("ad_placements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("buyer_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("seller_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("ad_text", sa.Text(), nullable=False),
        sa.Column("desired_at", sa.DateTime(timezone=True)),
        sa.Column("price_stars", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("published_message_id", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
    )
    for name, cols in [("ix_ad_orders_placement_id",["placement_id"]),("ix_ad_orders_buyer_telegram_id",["buyer_telegram_id"]),("ix_ad_orders_seller_telegram_id",["seller_telegram_id"]),("ix_ad_orders_status",["status"]),("ix_ad_orders_created_at",["created_at"]),("ix_ad_orders_desired_at",["desired_at"])]: op.create_index(name,"ad_orders",cols)
    op.create_table("group_subscription_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("plan_code", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for name, cols in [("ix_group_subscription_events_group_id",["group_id"]),("ix_group_subscription_events_actor_telegram_id",["actor_telegram_id"]),("ix_group_subscription_events_event_type",["event_type"]),("ix_group_subscription_events_created_at",["created_at"])]: op.create_index(name,"group_subscription_events",cols)

def downgrade():
    op.drop_table("group_subscription_events")
    op.drop_table("ad_orders")
    op.drop_table("ad_placements")
