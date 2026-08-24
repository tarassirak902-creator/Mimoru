from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group
from app.services.rank_access import get_actor_rank_with_access


async def _event_group_id(event: TelegramObject, data: dict[str, Any]) -> int | None:
    if isinstance(event, CallbackQuery) and isinstance(event.data, str):
        parts = event.data.split(":")
        if len(parts) >= 2 and parts[1].isdigit():
            return int(parts[1])
    state = data.get("state")
    if isinstance(event, Message) and isinstance(state, FSMContext):
        state_data = await state.get_data()
        group_id = state_data.get("group_id")
        if isinstance(group_id, int):
            return group_id
    return None


class RankAccessModeMiddleware(BaseMiddleware):
    """Fail closed when a rank router is reached through a stale access mode."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        session = data.get("session")
        bot = data.get("bot")
        if user is None or not isinstance(session, AsyncSession) or not isinstance(bot, Bot):
            return None

        group_id = await _event_group_id(event, data)
        if group_id is not None:
            group = await session.scalar(
                select(Group).where(Group.id == group_id, Group.is_active.is_(True))
            )
        elif isinstance(event, Message) and event.chat.type in {"group", "supergroup"}:
            group = await session.scalar(
                select(Group).where(
                    Group.telegram_chat_id == event.chat.id,
                    Group.is_active.is_(True),
                )
            )
        else:
            return await handler(event, data)

        if group is None or await get_actor_rank_with_access(bot, session, group, user.id) is None:
            if isinstance(event, CallbackQuery):
                await event.answer("Нет доступа или права администратора изменились.", show_alert=True)
            elif isinstance(event, Message):
                await event.answer("Доступ к управлению рангами потерян.")
            return None

        return await handler(event, data)
