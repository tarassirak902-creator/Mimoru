"""timezones and recurring schedules

Revision ID: 0011_timezones_and_recurring
Revises: 0010_operations_plus
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_timezones_and_recurring"
down_revision = "0010_operations_plus"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("group_settings", sa.Column("timezone_name", sa.String(length=64), nullable=False, server_default="Europe/Warsaw"))
    op.add_column("scheduled_messages", sa.Column("recurrence", sa.String(length=32), nullable=False, server_default="once"))
    op.add_column("scheduled_messages", sa.Column("recurrence_weekday", sa.Integer(), nullable=True))
    op.add_column("scheduled_messages", sa.Column("recurrence_time", sa.String(length=5), nullable=True))
    op.add_column("scheduled_messages", sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("scheduled_messages", "last_run_at")
    op.drop_column("scheduled_messages", "recurrence_time")
    op.drop_column("scheduled_messages", "recurrence_weekday")
    op.drop_column("scheduled_messages", "recurrence")
    op.drop_column("group_settings", "timezone_name")
