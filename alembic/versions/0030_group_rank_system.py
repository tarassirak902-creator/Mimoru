"""group rank system

Revision ID: 0030_group_rank_system
Revises: 0029_operations_center
"""
from alembic import op
import sqlalchemy as sa

revision = "0030_group_rank_system"
down_revision = "0029_operations_center"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rank_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("rank_code", sa.String(length=32), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("assigned_by_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("helper_for_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_admin_managed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("group_id", "user_telegram_id", name="uq_rank_assignment_group_user"),
    )
    for col in (
        "group_id",
        "user_telegram_id",
        "rank_code",
        "active",
        "assigned_by_telegram_id",
        "helper_for_telegram_id",
    ):
        op.create_index(f"ix_rank_assignments_{col}", "rank_assignments", [col])

    op.create_table(
        "group_rank_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rank_code", sa.String(length=32), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("updated_by_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("group_id", "rank_code", name="uq_group_rank_policy"),
    )
    op.create_index("ix_group_rank_policies_group_id", "group_rank_policies", ["group_id"])
    op.create_index("ix_group_rank_policies_rank_code", "group_rank_policies", ["rank_code"])

    op.create_table(
        "rank_assignment_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("target_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("old_rank_code", sa.String(length=32), nullable=True),
        sa.Column("new_rank_code", sa.String(length=32), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for col in ("group_id", "actor_telegram_id", "target_telegram_id", "action", "created_at"):
        op.create_index(f"ix_rank_assignment_events_{col}", "rank_assignment_events", [col])

    # Preserve existing internal roles during the transition to the new RBAC model.
    op.execute(
        sa.text(
            """
            INSERT INTO rank_assignments (
                group_id, user_telegram_id, rank_code, permissions, active,
                assigned_by_telegram_id, helper_for_telegram_id,
                telegram_admin_managed, created_at, updated_at
            )
            SELECT
                group_id,
                user_telegram_id,
                CASE role
                    WHEN 'senior' THEN 'chief_admin'
                    WHEN 'helper' THEN 'helper'
                    ELSE 'chat_admin'
                END,
                COALESCE(permissions, '{}'::json),
                active,
                assigned_by_telegram_id,
                NULL,
                FALSE,
                created_at,
                created_at
            FROM group_moderators
            ON CONFLICT (group_id, user_telegram_id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    for col in reversed(("group_id", "actor_telegram_id", "target_telegram_id", "action", "created_at")):
        op.drop_index(f"ix_rank_assignment_events_{col}", table_name="rank_assignment_events")
    op.drop_table("rank_assignment_events")
    op.drop_index("ix_group_rank_policies_rank_code", table_name="group_rank_policies")
    op.drop_index("ix_group_rank_policies_group_id", table_name="group_rank_policies")
    op.drop_table("group_rank_policies")
    for col in reversed((
        "group_id",
        "user_telegram_id",
        "rank_code",
        "active",
        "assigned_by_telegram_id",
        "helper_for_telegram_id",
    )):
        op.drop_index(f"ix_rank_assignments_{col}", table_name="rank_assignments")
    op.drop_table("rank_assignments")
