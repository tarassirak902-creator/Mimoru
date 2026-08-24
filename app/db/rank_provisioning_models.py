from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RankProvisioningIntent(Base):
    __tablename__ = "rank_provisioning_intents"
    __table_args__ = (
        UniqueConstraint("group_id", "user_telegram_id", name="uq_rank_provisioning_group_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    user_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    actor_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    operation: Mapped[str] = mapped_column(String(24), index=True)
    telegram_action: Mapped[str] = mapped_column(String(16), index=True)
    desired_rank_code: Mapped[str | None] = mapped_column(String(32))
    desired_access_mode: Mapped[str | None] = mapped_column(String(16))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )
