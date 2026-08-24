from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GroupMarriage(Base):
    __tablename__ = "group_marriages"
    __table_args__ = (
        UniqueConstraint("group_id", "user1_telegram_id", "user2_telegram_id", name="uq_group_marriage_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    user1_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user2_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GameEvent(Base):
    __tablename__ = "game_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(24), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    actor_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    target_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    actor_name: Mapped[str] = mapped_column(String(160))
    target_name: Mapped[str] = mapped_column(String(160))
    outcome: Mapped[str | None] = mapped_column(String(24), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class FunAutoImmunity(Base):
    __tablename__ = "fun_auto_immunity"
    __table_args__ = (
        UniqueConstraint("group_id", "user_telegram_id", name="uq_fun_auto_immunity_group_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    user_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FunGroupSettings(Base):
    __tablename__ = "fun_group_settings"
    __table_args__ = (UniqueConstraint("group_id", name="uq_fun_group_settings_group"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    auto_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    interval_code: Mapped[str] = mapped_column(String(16), default="15_20")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
