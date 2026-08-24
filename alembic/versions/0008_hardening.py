"""link whitelist and complaint review

Revision ID: 0008_hardening
Revises: 0007_operations
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_hardening"
down_revision = "0007_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "allowed_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("domain", sa.String(length=253), nullable=False),
        sa.Column("created_by_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("group_id", "domain", name="uq_allowed_links_group_domain"),
    )
    op.create_index("ix_allowed_links_group_id", "allowed_links", ["group_id"])
    op.add_column("complaints", sa.Column("reviewed_by_telegram_id", sa.BigInteger(), nullable=True))
    op.add_column("complaints", sa.Column("resolution", sa.Text(), nullable=True))
    op.add_column("complaints", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_complaints_status_group", "complaints", ["group_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_complaints_status_group", table_name="complaints")
    op.drop_column("complaints", "reviewed_at")
    op.drop_column("complaints", "resolution")
    op.drop_column("complaints", "reviewed_by_telegram_id")
    op.drop_index("ix_allowed_links_group_id", table_name="allowed_links")
    op.drop_table("allowed_links")
