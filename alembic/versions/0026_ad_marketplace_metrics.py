"""advertising marketplace metrics and lifecycle

Revision ID: 0026_ad_marketplace_metrics
Revises: 0025_group_members_deleted_accounts
"""
from alembic import op
import sqlalchemy as sa

revision = "0026_ad_marketplace_metrics"
down_revision = "0025_group_members_deleted_accounts"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("ad_placements", sa.Column("category", sa.String(length=32), nullable=False, server_default="general"))
    op.add_column("ad_placements", sa.Column("duration_hours", sa.Integer(), nullable=False, server_default="24"))
    op.add_column("ad_placements", sa.Column("member_count_snapshot", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ad_placements", sa.Column("avg_daily_messages_snapshot", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ad_placements", sa.Column("avg_daily_active_snapshot", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ad_placements", sa.Column("stats_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_ad_placements_category", "ad_placements", ["category"])
    op.add_column("ad_orders", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))

def downgrade() -> None:
    op.drop_column("ad_orders", "completed_at")
    op.drop_index("ix_ad_placements_category", table_name="ad_placements")
    op.drop_column("ad_placements", "stats_updated_at")
    op.drop_column("ad_placements", "avg_daily_active_snapshot")
    op.drop_column("ad_placements", "avg_daily_messages_snapshot")
    op.drop_column("ad_placements", "member_count_snapshot")
    op.drop_column("ad_placements", "duration_hours")
    op.drop_column("ad_placements", "category")
