"""automation center

Revision ID: 0028_automation_center
Revises: 0027_people_center
"""
from alembic import op
import sqlalchemy as sa

revision = "0028_automation_center"
down_revision = "0027_people_center"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("group_settings", sa.Column("automation_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("group_settings", sa.Column("deleted_cleanup_schedule", sa.String(length=16), nullable=False, server_default="off"))
    op.add_column("group_settings", sa.Column("deleted_cleanup_last_run_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "automation_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_code", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ok"),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_automation_logs_group_id", "automation_logs", ["group_id"])
    op.create_index("ix_automation_logs_rule_code", "automation_logs", ["rule_code"])
    op.create_index("ix_automation_logs_status", "automation_logs", ["status"])
    op.create_index("ix_automation_logs_created_at", "automation_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_automation_logs_created_at", table_name="automation_logs")
    op.drop_index("ix_automation_logs_status", table_name="automation_logs")
    op.drop_index("ix_automation_logs_rule_code", table_name="automation_logs")
    op.drop_index("ix_automation_logs_group_id", table_name="automation_logs")
    op.drop_table("automation_logs")
    op.drop_column("group_settings", "deleted_cleanup_last_run_at")
    op.drop_column("group_settings", "deleted_cleanup_schedule")
    op.drop_column("group_settings", "automation_enabled")
