from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group


_MUTATING_OWNER_COMMAND_RE = re.compile(
    r"^(?:"
    r"(?:антифлуд|ссылки|капча|приветствие) (?:вкл|выкл)"
    r"|добавить слово .+"
    r"|удалить слово .+"
    r"|добавить подписку @\w+"
    r"|удалить подписку @\w+"
    r")$",
    re.IGNORECASE,
)
_DELETE_WORDS = {"удалить", "стереть", "удали"}


class GroupMutationLockMiddleware(BaseMiddleware):
    """Serialize group-setting and moderation mutations on the primary router.

    This middleware replaces the old duplicate wrapper router. It acquires the
    Group row lock in the same transaction before the real production handler
    runs, so concurrent owner/rank/settings mutations cannot overwrite each
    other while dispatch remains single-path.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or not isinstance(event.text, str):
            return await handler(event, data)
        session = data.get("session")
        if not isinstance(session, AsyncSession):
            return await handler(event, data)

        text = " ".join(event.text.casefold().strip().split())
        needs_lock = bool(_MUTATING_OWNER_COMMAND_RE.fullmatch(text))
        if event.reply_to_message is not None and text in _DELETE_WORDS:
            needs_lock = True
        if not needs_lock:
            return await handler(event, data)

        await session.scalar(
            select(Group)
            .where(
                Group.telegram_chat_id == event.chat.id,
                Group.is_active.is_(True),
            )
            .with_for_update()
        )
        return await handler(event, data)
