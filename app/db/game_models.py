from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GameGroupSettings(Base):
    __tablename__ = "game_group_settings"

    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    allowed_games: Mapped[list] = mapped_column(JSON, default=list)
    creator_policy: Mapped[str] = mapped_column(String(24), default="lobby_creator")
    allow_duels: Mapped[bool] = mapped_column(Boolean, default=False)
    rating_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GamePanel(Base):
    __tablename__ = "game_panels"

    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True
    )
    message_id: Mapped[int] = mapped_column(BigInteger)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GameSession(Base):
    __tablename__ = "game_sessions"
    __table_args__ = (
        Index(
            "uq_game_sessions_one_active_per_group",
            "group_id",
            unique=True,
            postgresql_where=text("status IN ('lobby','running','recovering')"),
        ),
        Index("ix_game_sessions_deadline", "status", "deadline_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), index=True
    )
    game_type: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(16), default="lobby", index=True)
    phase: Mapped[str] = mapped_column(String(32), default="lobby", index=True)
    phase_seq: Mapped[int] = mapped_column(Integer, default=0)
    round_no: Mapped[int] = mapped_column(Integer, default=0)
    creator_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    exclusive_group_game: Mapped[bool] = mapped_column(Boolean, default=True)
    lobby_message_id: Mapped[int | None] = mapped_column(BigInteger)
    game_message_id: Mapped[int | None] = mapped_column(BigInteger)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    state_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    finish_reason: Mapped[str | None] = mapped_column(String(64))


class GamePlayer(Base):
    __tablename__ = "game_players"
    __table_args__ = (
        UniqueConstraint("game_id", "user_telegram_id", name="uq_game_players_game_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"), index=True
    )
    user_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    display_name: Mapped[str] = mapped_column(String(160), default="")
    role: Mapped[str | None] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(16), default="joined", index=True)
    team: Mapped[str | None] = mapped_column(String(32), index=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    afk_count: Mapped[int] = mapped_column(Integer, default=0)
    state_json: Mapped[dict] = mapped_column(JSON, default=dict)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GameAction(Base):
    __tablename__ = "game_actions"
    __table_args__ = (
        UniqueConstraint(
            "game_id",
            "phase_seq",
            "actor_telegram_id",
            "action_type",
            name="uq_game_action_once_per_phase",
        ),
        Index("ix_game_actions_game_phase", "game_id", "phase_seq"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"), index=True
    )
    round_no: Mapped[int] = mapped_column(Integer, default=0)
    phase_seq: Mapped[int] = mapped_column(Integer)
    actor_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    action_type: Mapped[str] = mapped_column(String(32), index=True)
    target_telegram_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GameTargetMap(Base):
    __tablename__ = "game_target_maps"
    __table_args__ = (
        UniqueConstraint(
            "game_id",
            "phase_seq",
            "actor_telegram_id",
            "number",
            name="uq_game_target_map_number",
        ),
        UniqueConstraint(
            "game_id",
            "phase_seq",
            "actor_telegram_id",
            "target_telegram_id",
            name="uq_game_target_map_target",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"), index=True
    )
    phase_seq: Mapped[int] = mapped_column(Integer, index=True)
    actor_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    number: Mapped[int] = mapped_column(Integer)
    target_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GameMessage(Base):
    __tablename__ = "game_messages"
    __table_args__ = (
        UniqueConstraint("game_id", "message_id", name="uq_game_messages_game_message"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"), index=True
    )
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    message_id: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(24), default="temporary", index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GamePlayerStats(Base):
    __tablename__ = "game_player_stats"
    __table_args__ = (
        UniqueConstraint("group_id", "user_telegram_id", name="uq_game_player_stats_group_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), index=True
    )
    user_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    games_played: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[int] = mapped_column(Integer, default=1000, index=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    win_streak: Mapped[int] = mapped_column(Integer, default=0)
    best_win_streak: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GamePlayerGameStats(Base):
    __tablename__ = "game_player_game_stats"
    __table_args__ = (
        UniqueConstraint(
            "group_id",
            "user_telegram_id",
            "game_type",
            name="uq_game_player_game_stats_group_user_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), index=True
    )
    user_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    game_type: Mapped[str] = mapped_column(String(32), index=True)
    games_played: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[int] = mapped_column(Integer, default=1000)
    score: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GameResult(Base):
    __tablename__ = "game_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"), unique=True, index=True
    )
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), index=True
    )
    game_type: Mapped[str] = mapped_column(String(32), index=True)
    winner_type: Mapped[str | None] = mapped_column(String(32), index=True)
    winner_json: Mapped[dict] = mapped_column(JSON, default=dict)
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
