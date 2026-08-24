"""client management and promo codes

Revision ID: 0013_client_management
Revises: 0012_audit_delivery
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_client_management"
down_revision = "0012_audit_delivery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("service_blocked", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("ix_users_service_blocked", "users", ["service_blocked"])
    op.create_table(
        "promo_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("plan_code", sa.String(length=32), nullable=False, server_default="standard"),
        sa.Column("bonus_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("max_uses", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("current_uses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_promo_codes_code", "promo_codes", ["code"], unique=True)
    op.create_index("ix_promo_codes_active", "promo_codes", ["active"])
    op.create_table(
        "promo_code_uses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("promo_code_id", sa.Integer(), sa.ForeignKey("promo_codes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("promo_code_id", "user_telegram_id", name="uq_promo_user"),
    )
    op.create_index("ix_promo_code_uses_promo_code_id", "promo_code_uses", ["promo_code_id"])
    op.create_index("ix_promo_code_uses_user_telegram_id", "promo_code_uses", ["user_telegram_id"])
    op.create_index("ix_promo_code_uses_group_id", "promo_code_uses", ["group_id"])


def downgrade() -> None:
    op.drop_table("promo_code_uses")
    op.drop_table("promo_codes")
    op.drop_index("ix_users_service_blocked", table_name="users")
    op.drop_column("users", "service_blocked")
