"""payment integrity indexes

Revision ID: 0006_payment_integrity
Revises: 0005_payments
"""
from alembic import op

revision = "0006_payment_integrity"
down_revision = "0005_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_payments_user_status", "payments", ["user_telegram_id", "status"], unique=False)
    op.create_index("ix_payments_group_created", "payments", ["group_id", "created_at"], unique=False)
    op.create_index("ix_punishments_active_ends", "punishments", ["active", "ends_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_punishments_active_ends", table_name="punishments")
    op.drop_index("ix_payments_group_created", table_name="payments")
    op.drop_index("ix_payments_user_status", table_name="payments")
