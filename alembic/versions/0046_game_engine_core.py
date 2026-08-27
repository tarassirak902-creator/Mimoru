"""game engine core

Revision ID: 0046_game_engine_core
Revises: 0045_moderation_command_modes
"""
from alembic import op
import sqlalchemy as sa

revision = "0046_game_engine_core"
down_revision = "0045_moderation_command_modes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_group_settings",
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allowed_games", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("creator_policy", sa.String(length=24), nullable=False, server_default="lobby_creator"),
        sa.Column("allow_duels", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rating_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("settings_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "game_panels",
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "game_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("game_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="lobby"),
        sa.Column("phase", sa.String(length=32), nullable=False, server_default="lobby"),
        sa.Column("phase_seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("round_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("creator_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("exclusive_group_game", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("lobby_message_id", sa.BigInteger(), nullable=True),
        sa.Column("game_message_id", sa.BigInteger(), nullable=True),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finish_reason", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_game_sessions_group_id", "game_sessions", ["group_id"])
    op.create_index("ix_game_sessions_game_type", "game_sessions", ["game_type"])
    op.create_index("ix_game_sessions_status", "game_sessions", ["status"])
    op.create_index("ix_game_sessions_phase", "game_sessions", ["phase"])
    op.create_index("ix_game_sessions_deadline_at", "game_sessions", ["deadline_at"])
    op.create_index("ix_game_sessions_finished_at", "game_sessions", ["finished_at"])
    op.create_index("ix_game_sessions_deadline", "game_sessions", ["status", "deadline_at"])
    op.create_index(
        "uq_game_sessions_one_active_per_group",
        "game_sessions",
        ["group_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('lobby','running','recovering')"),
    )

    op.create_table(
        "game_players",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("role", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="joined"),
        sa.Column("team", sa.String(length=32), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("afk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("state_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("game_id", "user_telegram_id", name="uq_game_players_game_user"),
    )
    op.create_index("ix_game_players_game_id", "game_players", ["game_id"])
    op.create_index("ix_game_players_user_telegram_id", "game_players", ["user_telegram_id"])
    op.create_index("ix_game_players_role", "game_players", ["role"])
    op.create_index("ix_game_players_status", "game_players", ["status"])
    op.create_index("ix_game_players_team", "game_players", ["team"])

    op.create_table(
        "game_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("round_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("phase_seq", sa.Integer(), nullable=False),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("target_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("game_id", "phase_seq", "actor_telegram_id", "action_type", name="uq_game_action_once_per_phase"),
    )
    op.create_index("ix_game_actions_game_id", "game_actions", ["game_id"])
    op.create_index("ix_game_actions_actor_telegram_id", "game_actions", ["actor_telegram_id"])
    op.create_index("ix_game_actions_action_type", "game_actions", ["action_type"])
    op.create_index("ix_game_actions_target_telegram_id", "game_actions", ["target_telegram_id"])
    op.create_index("ix_game_actions_game_phase", "game_actions", ["game_id", "phase_seq"])

    op.create_table(
        "game_target_maps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phase_seq", sa.Integer(), nullable=False),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("target_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("game_id", "phase_seq", "actor_telegram_id", "number", name="uq_game_target_map_number"),
        sa.UniqueConstraint("game_id", "phase_seq", "actor_telegram_id", "target_telegram_id", name="uq_game_target_map_target"),
    )
    op.create_index("ix_game_target_maps_game_id", "game_target_maps", ["game_id"])
    op.create_index("ix_game_target_maps_phase_seq", "game_target_maps", ["phase_seq"])
    op.create_index("ix_game_target_maps_actor_telegram_id", "game_target_maps", ["actor_telegram_id"])
    op.create_index("ix_game_target_maps_target_telegram_id", "game_target_maps", ["target_telegram_id"])

    op.create_table(
        "game_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False, server_default="temporary"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("game_id", "message_id", name="uq_game_messages_game_message"),
    )
    op.create_index("ix_game_messages_game_id", "game_messages", ["game_id"])
    op.create_index("ix_game_messages_chat_id", "game_messages", ["chat_id"])
    op.create_index("ix_game_messages_kind", "game_messages", ["kind"])
    op.create_index("ix_game_messages_active", "game_messages", ["active"])

    op.create_table(
        "game_player_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("games_played", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rating", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("win_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("best_win_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("group_id", "user_telegram_id", name="uq_game_player_stats_group_user"),
    )
    op.create_index("ix_game_player_stats_group_id", "game_player_stats", ["group_id"])
    op.create_index("ix_game_player_stats_user_telegram_id", "game_player_stats", ["user_telegram_id"])
    op.create_index("ix_game_player_stats_rating", "game_player_stats", ["rating"])

    op.create_table(
        "game_player_game_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("game_type", sa.String(length=32), nullable=False),
        sa.Column("games_played", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rating", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("group_id", "user_telegram_id", "game_type", name="uq_game_player_game_stats_group_user_type"),
    )
    op.create_index("ix_game_player_game_stats_group_id", "game_player_game_stats", ["group_id"])
    op.create_index("ix_game_player_game_stats_user_telegram_id", "game_player_game_stats", ["user_telegram_id"])
    op.create_index("ix_game_player_game_stats_game_type", "game_player_game_stats", ["game_type"])

    op.create_table(
        "game_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("game_type", sa.String(length=32), nullable=False),
        sa.Column("winner_type", sa.String(length=32), nullable=True),
        sa.Column("winner_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("summary_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_game_results_game_id", "game_results", ["game_id"])
    op.create_index("ix_game_results_group_id", "game_results", ["group_id"])
    op.create_index("ix_game_results_game_type", "game_results", ["game_type"])
    op.create_index("ix_game_results_winner_type", "game_results", ["winner_type"])


def downgrade() -> None:
    op.drop_table("game_results")
    op.drop_table("game_player_game_stats")
    op.drop_table("game_player_stats")
    op.drop_table("game_messages")
    op.drop_table("game_target_maps")
    op.drop_table("game_actions")
    op.drop_table("game_players")
    op.drop_table("game_sessions")
    op.drop_table("game_panels")
    op.drop_table("game_group_settings")
