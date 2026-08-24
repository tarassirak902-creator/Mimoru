from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InviteOperation(Base):
    __tablename__ = "invite_operations"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("invite_campaigns.id", ondelete="SET NULL"), index=True
    )
    operation: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    name: Mapped[str | None] = mapped_column(String(64))
    invite_link: Mapped[str | None] = mapped_column(String(255), index=True)
    creates_join_request: Mapped[bool | None] = mapped_column(Boolean)
    actor_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    error_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
