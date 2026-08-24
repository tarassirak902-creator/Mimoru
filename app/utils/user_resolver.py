from __future__ import annotations

from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GroupMember, User
from app.services.public_identity import public_user_token


def _extract_raw_target(message: Message, command_len: int) -> str | None:
    """Extract text after the command keyword, if any."""
    text = message.text or ""
    tail = text[command_len:].strip()
    return tail if tail else None


def _is_reply_target(message: Message) -> int | None:
    """Return the replied-to user ID if message is a reply, else None."""
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id
    return None


async def _resolve_username(session: AsyncSession, group_id: int, username: str) -> int | None:
    """Look up a @username in the group's member history."""
    clean = username.lstrip("@").casefold()
    if not clean:
        return None
    row = await session.execute(
        select(User.telegram_id)
        .join(GroupMember, GroupMember.user_telegram_id == User.telegram_id)
        .where(
            GroupMember.group_id == group_id,
            func.lower(User.username) == clean,
        )
        .limit(1)
    )
    found = row.scalar_one_or_none()
    return int(found) if found is not None else None


async def resolve_target_user(
    session: AsyncSession,
    group_id: int,
    message: Message,
    *,
    command_keyword: str,
) -> tuple[int | None, str]:
    """Unified user resolution: reply → @username → numeric Telegram ID.

    Priority order:
    1. Reply (message.reply_to_message.from_user.id)
    2. @username from text after command_keyword
    3. Numeric Telegram ID from text after command_keyword

    Returns (target_id, target_label) or (None, error_hint).

    ``command_keyword`` is the lowercase command word to skip, e.g. ``"мут"``,
    ``"размут"``, ``"бан"``.  The keyword is matched case-insensitively and
    stripped of surrounding whitespace.
    """
    # 1. Reply — highest priority
    reply_id = _is_reply_target(message)
    if reply_id is not None:
        return reply_id, public_user_token(reply_id)

    # 2 & 3. Extract argument from message text
    text = (message.text or "").strip()
    lowered = text.casefold()
    kw = command_keyword.casefold()
    if lowered.startswith(kw):
        tail = text[len(kw):].strip()
    else:
        tail = ""
    if not tail:
        return None, ""

    # 2. @username
    if tail.startswith("@"):
        uid = await _resolve_username(session, group_id, tail)
        if uid is not None:
            return uid, public_user_token(uid)
        return None, f"Пользователь {tail} не найден в истории группы."

    # 3. Numeric Telegram ID
    if tail.isdigit():
        target_id = int(tail)
        return target_id, public_user_token(target_id)

    # Try as bare username (without @)
    uid = await _resolve_username(session, group_id, tail)
    if uid is not None:
        return uid, public_user_token(uid)

    return None, "Не удалось определить пользователя. Используйте реплай, @username или числовой Telegram ID."
