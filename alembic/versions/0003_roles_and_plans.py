"""roles and basic plans"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("groups", sa.Column("plan_code", sa.String(length=32), nullable=False, server_default="trial"))
    op.add_column("groups", sa.Column("plan_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "group_moderators",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="moderator"),
        sa.Column("permissions", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("assigned_by_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("group_id", "user_telegram_id"),
    )
    op.create_index("ix_group_moderators_group_id", "group_moderators", ["group_id"])
    op.create_index("ix_group_moderators_user_telegram_id", "group_moderators", ["user_telegram_id"])


def downgrade():
    op.drop_index("ix_group_moderators_user_telegram_id", table_name="group_moderators")
    op.drop_index("ix_group_moderators_group_id", table_name="group_moderators")
    op.drop_table("group_moderators")
    op.drop_column("groups", "plan_expires_at")
    op.drop_column("groups", "plan_code")
