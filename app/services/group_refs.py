from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group


async def telegram_group_identity(bot: Bot, group: Group) -> tuple[int, str | None]:
    """Return Telegram chat id and current public @username when available."""
    try:
        chat = await bot.get_chat(group.telegram_chat_id)
    except (TelegramBadRequest, TelegramForbiddenError):
        return group.telegram_chat_id, None
    username = getattr(chat, "username", None)
    return group.telegram_chat_id, (f"@{username}" if username else None)


async def group_reference_label(bot: Bot, group: Group) -> str:
    """Human-facing group label. Telegram/internal IDs stay hidden from UI."""
    try:
        chat = await bot.get_chat(group.telegram_chat_id)
    except (TelegramBadRequest, TelegramForbiddenError):
        return group.title or "Группа"
    title = getattr(chat, "title", None) or group.title or "Группа"
    username = getattr(chat, "username", None)
    return f"{title} · @{username}" if username else title


async def resolve_group_reference(
    session: AsyncSession,
    bot: Bot,
    raw_reference: str,
    *,
    owner_telegram_id: int | None = None,
    active_only: bool = True,
) -> Group | None:
    """Resolve a connected Mimoru group by Telegram ID, internal ID or @username.

    Numeric identifiers remain accepted for commands and internal compatibility,
    but are not shown in normal user-facing screens.
    """
    value = (raw_reference or "").strip()
    if not value:
        return None

    query = select(Group)
    if active_only:
        query = query.where(Group.is_active.is_(True))
    if owner_telegram_id is not None:
        query = query.where(Group.owner_telegram_id == owner_telegram_id)

    if value.lstrip("-").isdigit():
        number = int(value)
        return await session.scalar(
            query.where(or_(Group.telegram_chat_id == number, Group.id == number))
        )

    username = value if value.startswith("@") else f"@{value}"
    try:
        chat = await bot.get_chat(username)
    except (TelegramBadRequest, TelegramForbiddenError):
        return None
    return await session.scalar(query.where(Group.telegram_chat_id == chat.id))
