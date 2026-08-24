"""people center

Revision ID: 0027_people_center
Revises: 0026_ad_marketplace_metrics
"""
from alembic import op
import sqlalchemy as sa

revision = "0027_people_center"
down_revision = "0026_ad_marketplace_metrics"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("group_members", sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("group_members", sa.Column("reputation_override", sa.Integer(), nullable=True))
    op.add_column("group_members", sa.Column("trust_status", sa.String(length=32), nullable=True))
    op.create_index("ix_group_members_joined_at", "group_members", ["joined_at"])
    op.create_index("ix_group_members_trust_status", "group_members", ["trust_status"])
    op.create_table("member_tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=48), nullable=False),
        sa.Column("created_by_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("group_id", "name", name="uq_member_tags_group_name"),
    )
    op.create_index("ix_member_tags_group_id", "member_tags", ["group_id"])
    op.create_table("member_tag_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("member_tags.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_by_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("group_id", "user_telegram_id", "tag_id", name="uq_member_tag_assignment"),
    )
    op.create_index("ix_member_tag_assignments_group_id", "member_tag_assignments", ["group_id"])
    op.create_index("ix_member_tag_assignments_user_telegram_id", "member_tag_assignments", ["user_telegram_id"])
    op.create_index("ix_member_tag_assignments_tag_id", "member_tag_assignments", ["tag_id"])
    op.create_table("user_profile_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("last_name", sa.String(length=128), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_user_profile_history_user_telegram_id", "user_profile_history", ["user_telegram_id"])
    op.create_index("ix_user_profile_history_recorded_at", "user_profile_history", ["recorded_at"])

def downgrade() -> None:
    op.drop_table("user_profile_history")
    op.drop_table("member_tag_assignments")
    op.drop_table("member_tags")
    op.drop_index("ix_group_members_trust_status", table_name="group_members")
    op.drop_index("ix_group_members_joined_at", table_name="group_members")
    op.drop_column("group_members", "trust_status")
    op.drop_column("group_members", "reputation_override")
    op.drop_column("group_members", "joined_at")
