"""operations and scheduled reports

Revision ID: 0007_operations
Revises: 0006_payment_integrity
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_operations"
down_revision = "0006_payment_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("group_settings", sa.Column("reports_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("group_settings", sa.Column("report_hour_utc", sa.Integer(), nullable=False, server_default="8"))
    op.add_column("group_settings", sa.Column("last_report_date", sa.String(length=10), nullable=True))
    op.create_table(
        "broadcasts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("sent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_broadcasts_actor", "broadcasts", ["actor_telegram_id"])
    op.create_index("ix_broadcasts_status", "broadcasts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_broadcasts_status", table_name="broadcasts")
    op.drop_index("ix_broadcasts_actor", table_name="broadcasts")
    op.drop_table("broadcasts")
    op.drop_column("group_settings", "last_report_date")
    op.drop_column("group_settings", "report_hour_utc")
    op.drop_column("group_settings", "reports_enabled")
