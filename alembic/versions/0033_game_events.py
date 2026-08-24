"""game event journal

Revision ID: 0033_game_events
Revises: 0032_group_marriages
"""
from alembic import op
import sqlalchemy as sa

revision = "0033_game_events"
down_revision = "0032_group_marriages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("target_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_name", sa.String(length=160), nullable=False),
        sa.Column("target_name", sa.String(length=160), nullable=False),
        sa.Column("outcome", sa.String(length=24), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_game_events_group_id", "game_events", ["group_id"])
    op.create_index("ix_game_events_event_type", "game_events", ["event_type"])
    op.create_index("ix_game_events_action", "game_events", ["action"])
    op.create_index("ix_game_events_actor_telegram_id", "game_events", ["actor_telegram_id"])
    op.create_index("ix_game_events_target_telegram_id", "game_events", ["target_telegram_id"])
    op.create_index("ix_game_events_outcome", "game_events", ["outcome"])
    op.create_index("ix_game_events_created_at", "game_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_game_events_created_at", table_name="game_events")
    op.drop_index("ix_game_events_outcome", table_name="game_events")
    op.drop_index("ix_game_events_target_telegram_id", table_name="game_events")
    op.drop_index("ix_game_events_actor_telegram_id", table_name="game_events")
    op.drop_index("ix_game_events_action", table_name="game_events")
    op.drop_index("ix_game_events_event_type", table_name="game_events")
    op.drop_index("ix_game_events_group_id", table_name="game_events")
    op.drop_table("game_events")
