"""track known group members and deleted Telegram accounts

Revision ID: 0025_group_members_deleted_accounts
Revises: 0024_moderation_reasons
"""
from alembic import op
import sqlalchemy as sa

revision = "0025_group_members_deleted_accounts"
down_revision = "0024_moderation_reasons"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "group_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("is_present", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_deleted_account", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("group_id", "user_telegram_id", name="uq_group_members_group_user"),
    )
    op.create_index("ix_group_members_group_id", "group_members", ["group_id"])
    op.create_index("ix_group_members_user_telegram_id", "group_members", ["user_telegram_id"])
    op.create_index("ix_group_members_is_present", "group_members", ["is_present"])
    op.create_index("ix_group_members_is_deleted_account", "group_members", ["is_deleted_account"])

    # Backfill IDs Mimoru has already observed so the first scan is useful immediately.
    op.execute("""
        INSERT INTO group_members (group_id, user_telegram_id, is_present, is_deleted_account)
        SELECT DISTINCT group_id, user_telegram_id, TRUE, FALSE
        FROM (
            SELECT group_id, user_telegram_id FROM daily_stats
            UNION
            SELECT group_id, user_telegram_id FROM new_member_records
            UNION
            SELECT group_id, user_telegram_id FROM warnings
            UNION
            SELECT group_id, user_telegram_id FROM punishments
            UNION
            SELECT group_id, user_telegram_id FROM group_moderators
        ) observed
        WHERE user_telegram_id IS NOT NULL
        ON CONFLICT (group_id, user_telegram_id) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index("ix_group_members_is_deleted_account", table_name="group_members")
    op.drop_index("ix_group_members_is_present", table_name="group_members")
    op.drop_index("ix_group_members_user_telegram_id", table_name="group_members")
    op.drop_index("ix_group_members_group_id", table_name="group_members")
    op.drop_table("group_members")
