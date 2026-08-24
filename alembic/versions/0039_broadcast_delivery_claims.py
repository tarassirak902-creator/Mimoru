"""durable broadcast execution and delivery claims

Revision ID: 0039_broadcast_delivery_claims
Revises: 0038_pending_bans
"""
from alembic import op
import sqlalchemy as sa

revision = "0039_broadcast_delivery_claims"
down_revision = "0038_pending_bans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "broadcast_executions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_token", sa.String(length=64), nullable=False),
        sa.Column(
            "broadcast_id",
            sa.Integer(),
            sa.ForeignKey("broadcasts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("request_token", name="uq_broadcast_executions_request_token"),
        sa.UniqueConstraint("broadcast_id", name="uq_broadcast_executions_broadcast_id"),
    )
    op.create_index(
        "ix_broadcast_executions_request_token",
        "broadcast_executions",
        ["request_token"],
    )
    op.create_index(
        "ix_broadcast_executions_broadcast_id",
        "broadcast_executions",
        ["broadcast_id"],
    )
    op.create_index(
        "ix_broadcast_executions_created_at",
        "broadcast_executions",
        ["created_at"],
    )

    op.create_table(
        "broadcast_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "broadcast_id",
            sa.Integer(),
            sa.ForeignKey("broadcasts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "group_id",
            sa.Integer(),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="processing"),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "broadcast_id",
            "group_id",
            name="uq_broadcast_delivery_group",
        ),
    )
    op.create_index(
        "ix_broadcast_deliveries_broadcast_id",
        "broadcast_deliveries",
        ["broadcast_id"],
    )
    op.create_index(
        "ix_broadcast_deliveries_group_id",
        "broadcast_deliveries",
        ["group_id"],
    )
    op.create_index(
        "ix_broadcast_deliveries_status",
        "broadcast_deliveries",
        ["status"],
    )
    op.create_index(
        "ix_broadcast_deliveries_created_at",
        "broadcast_deliveries",
        ["created_at"],
    )
    op.create_index(
        "ix_broadcast_deliveries_finished_at",
        "broadcast_deliveries",
        ["finished_at"],
    )


def downgrade() -> None:
    op.drop_table("broadcast_deliveries")
    op.drop_table("broadcast_executions")
