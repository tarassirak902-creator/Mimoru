"""advertising order payments

Revision ID: 0023_ad_order_payments
Revises: 0022_commercial_panels_and_ads
"""
from alembic import op
import sqlalchemy as sa

revision = "0023_ad_order_payments"
down_revision = "0022_commercial_panels_and_ads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ad_orders", sa.Column("payment_charge_id", sa.String(255), nullable=True))
    op.add_column("ad_orders", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint(
        "uq_ad_orders_payment_charge_id", "ad_orders", ["payment_charge_id"]
    )
    op.create_index("ix_ad_orders_paid_at", "ad_orders", ["paid_at"])


def downgrade() -> None:
    op.drop_index("ix_ad_orders_paid_at", table_name="ad_orders")
    op.drop_constraint("uq_ad_orders_payment_charge_id", "ad_orders", type_="unique")
    op.drop_column("ad_orders", "paid_at")
    op.drop_column("ad_orders", "payment_charge_id")
