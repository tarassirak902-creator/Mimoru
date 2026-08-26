from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group
from app.handlers import group_action_aliases
from app.services.rank_access import get_actor_rank_with_access


_SENSITIVE_ALIAS_WORDS = (
    group_action_aliases.GROUP_STATS_ALIASES
    | group_action_aliases.ALL_BANS_ALIASES
    | group_action_aliases.ALL_MUTES_ALIASES
    | group_action_aliases.ALL_WARNINGS_ALIASES
    | group_action_aliases.MY_BANS_ALIASES
    | group_action_aliases.MY_MUTES_ALIASES
    | group_action_aliases.MY_WARNINGS_ALIASES
)
_RANK_MUTATION_PREFIXES = ("rank_perm:", "rank_reset:")
_MEDIA_MUTATION_WORDS = {"без медиа", "медиа выкл", "медиа вкл"}


class SensitiveGroupAliasAccessMiddleware(BaseMiddleware):
    """Validate live rank access for administration-only group aliases."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or not isinstance(event.text, str):
            return await handler(event, data)
        text = " ".join(event.text.casefold().strip().split())
        if text not in _SENSITIVE_ALIAS_WORDS:
            return await handler(event, data)

        user = event.from_user
        session = data.get("session")
        bot = data.get("bot")
        if user is None or not isinstance(session, AsyncSession) or not isinstance(bot, Bot):
            return None
        group = await session.scalar(
            select(Group).where(
                Group.telegram_chat_id == event.chat.id,
                Group.is_active.is_(True),
            )
        )
        actor = None if group is None else await get_actor_rank_with_access(bot, session, group, user.id)
        if actor is None or actor.code not in group_action_aliases.ADMIN_INFO_RANKS:
            await event.reply("Эта информация доступна только администрации Mimoru этой группы.")
            if text in group_action_aliases.GROUP_STATS_ALIASES:
                await event.reply("Свою личную информацию можно посмотреть фразой «кто я» или «моя стата».")
            return None
        return await handler(event, data)


class RankMutationLockMiddleware(BaseMiddleware):
    """Serialize rank mutations with owner/rank authority changes."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session = data.get("session")
        if not isinstance(session, AsyncSession):
            return await handler(event, data)

        group_id: int | None = None
        chat_id: int | None = None
        if isinstance(event, CallbackQuery) and isinstance(event.data, str):
            if event.data.startswith(_RANK_MUTATION_PREFIXES):
                parts = event.data.split(":")
                if len(parts) >= 2 and parts[1].isdigit():
                    group_id = int(parts[1])
        elif isinstance(event, Message) and isinstance(event.text, str):
            text = " ".join(event.text.casefold().strip().split())
            if event.reply_to_message is not None and text in _MEDIA_MUTATION_WORDS:
                chat_id = event.chat.id

        if group_id is not None:
            await session.scalar(
                select(Group)
                .where(Group.id == group_id, Group.is_active.is_(True))
                .with_for_update()
            )
        elif chat_id is not None:
            await session.scalar(
                select(Group)
                .where(
                    Group.telegram_chat_id == chat_id,
                    Group.is_active.is_(True),
                )
                .with_for_update()
            )
        return await handler(event, data)
