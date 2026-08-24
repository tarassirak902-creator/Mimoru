"""operations center

Revision ID: 0029_operations_center
Revises: 0028_automation_center
"""
from alembic import op
import sqlalchemy as sa

revision = "0029_operations_center"
down_revision = "0028_automation_center"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "operation_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ok"),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("target_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for col in ("group_id","event_type","status","actor_telegram_id","target_telegram_id","created_at"):
        op.create_index(f"ix_operation_events_{col}", "operation_events", [col])
    op.create_table(
        "group_config_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False, server_default="Резервная копия"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_by_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_group_config_snapshots_group_id", "group_config_snapshots", ["group_id"])
    op.create_index("ix_group_config_snapshots_created_by_telegram_id", "group_config_snapshots", ["created_by_telegram_id"])
    op.create_index("ix_group_config_snapshots_created_at", "group_config_snapshots", ["created_at"])

def downgrade() -> None:
    op.drop_index("ix_group_config_snapshots_created_at", table_name="group_config_snapshots")
    op.drop_index("ix_group_config_snapshots_created_by_telegram_id", table_name="group_config_snapshots")
    op.drop_index("ix_group_config_snapshots_group_id", table_name="group_config_snapshots")
    op.drop_table("group_config_snapshots")
    for col in reversed(("group_id","event_type","status","actor_telegram_id","target_telegram_id","created_at")):
        op.drop_index(f"ix_operation_events_{col}", table_name="operation_events")
    op.drop_table("operation_events")
