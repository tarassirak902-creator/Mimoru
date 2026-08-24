"""deleted cleanup retry ledger

Revision ID: 0043_deleted_cleanup_retries
Revises: 0042_invite_operations
"""
from alembic import op
import sqlalchemy as sa

revision = "0043_deleted_cleanup_retries"
down_revision = "0042_invite_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deleted_cleanup_retries",
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("retry_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_deleted_cleanup_retries_retry_at", "deleted_cleanup_retries", ["retry_at"])


def downgrade() -> None:
    op.drop_table("deleted_cleanup_retries")
