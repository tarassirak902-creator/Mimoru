from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.services.public_identity import public_user_token


def user_display_name(user: User | None, telegram_id: int | None = None) -> str:
    if user is None:
        return "Неизвестный пользователь"
    full_name = " ".join(part for part in (user.first_name, user.last_name) if part).strip()
    if full_name and user.username:
        return f"{full_name} · @{user.username}"
    if full_name:
        return full_name
    if user.username:
        return f"@{user.username}"
    return "Пользователь"


async def user_label(session: AsyncSession, telegram_id: int) -> str:
    """Return a user-facing identity placeholder, never a raw numeric Telegram ID.

    PlainTextBot resolves this placeholder immediately before Telegram delivery using the
    current group profile when available,     then Mimoru's last stored Telegram name/username.
    """

    return public_user_token(telegram_id)


async def resolve_known_user_reference(
    session: AsyncSession,
    raw_reference: str,
) -> tuple[int | None, str | None]:
    """Resolve an ID or a username already known to Mimoru.

    Returns (telegram_id, normalized_username). For an unknown @username,
    telegram_id is None while normalized_username is preserved so callers can
    create a deferred rule that will resolve when the account is first seen.
    """
    value = (raw_reference or "").strip()
    if not value:
        return None, None
    if value.isdigit():
        return int(value), None
    if not value.startswith("@") or len(value) < 2:
        return None, None
    username = value[1:].strip().casefold()
    if not username:
        return None, None
    user = await session.scalar(
        select(User).where(func.lower(User.username) == username).order_by(User.id.desc()).limit(1)
    )
    return (user.telegram_id if user is not None else None), username
