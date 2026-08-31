from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.games.handlers import GROUP_TYPES, _active_group
from app.games.panels import ensure_game_panel


router = Router(name=__name__)


@router.message(F.chat.type.in_(GROUP_TYPES), F.text.regexp(r"(?i)^игры$"))
async def games_text_entry(message: Message, bot: Bot, session: AsyncSession) -> None:
    group = await _active_group(session, message.chat.id)
    if group is None:
        return
    await ensure_game_panel(bot, session, group=group)
