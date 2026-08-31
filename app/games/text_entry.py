from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.games.handlers import GROUP_TYPES, _active_group
from app.games.panels import active_game_for_group, ensure_game_panel, panel_markup, panel_text


router = Router(name=__name__)


async def _show_game_center(message: Message, bot: Bot, session: AsyncSession) -> None:
    group = await _active_group(session, message.chat.id)
    if group is None:
        return
    await ensure_game_panel(bot, session, group=group)
    active_game = await active_game_for_group(session, group.id)
    await bot.send_message(
        group.telegram_chat_id,
        panel_text(active_game=active_game),
        reply_markup=panel_markup(active_game=active_game),
        reply_to_message_id=message.message_id,
    )


@router.message(Command("games"), F.chat.type.in_(GROUP_TYPES))
async def games_command_entry(message: Message, bot: Bot, session: AsyncSession) -> None:
    await _show_game_center(message, bot, session)


@router.message(F.chat.type.in_(GROUP_TYPES), F.text.regexp(r"(?i)^игры$"))
async def games_text_entry(message: Message, bot: Bot, session: AsyncSession) -> None:
    await _show_game_center(message, bot, session)
