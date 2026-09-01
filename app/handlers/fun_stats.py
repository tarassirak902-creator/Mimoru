from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group
from app.games.stat_views import render_group_game_stats


router = Router(name=__name__)
GROUP_TYPES = {"group", "supergroup"}
GAME_STATS_ALIASES = {"стата игр", "статистика игр"}


@router.message(F.chat.type.in_(GROUP_TYPES), F.text.casefold().in_(GAME_STATS_ALIASES))
async def game_statistics(message: Message, session: AsyncSession) -> None:
    group = await session.scalar(
        select(Group).where(
            Group.telegram_chat_id == message.chat.id,
            Group.is_active.is_(True),
        )
    )
    if group is None:
        return
    await message.reply(await render_group_game_stats(session, group_id=group.id))
