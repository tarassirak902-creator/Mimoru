"""moderation logs"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "moderation_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("target_telegram_id", sa.BigInteger()),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_moderation_logs_group_id", "moderation_logs", ["group_id"])
    op.create_index("ix_moderation_logs_actor_telegram_id", "moderation_logs", ["actor_telegram_id"])
    op.create_index("ix_moderation_logs_target_telegram_id", "moderation_logs", ["target_telegram_id"])
    op.create_index("ix_moderation_logs_action", "moderation_logs", ["action"])
    op.create_index("ix_moderation_logs_created_at", "moderation_logs", ["created_at"])


def downgrade():
    op.drop_table("moderation_logs")
