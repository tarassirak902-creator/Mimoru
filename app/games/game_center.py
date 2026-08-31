from __future__ import annotations

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group
from app.games.panels import active_game_for_group, ensure_game_panel, panel_markup, panel_text


async def send_game_center_snapshot(
    bot: Bot,
    session: AsyncSession,
    *,
    group: Group,
    reply_to_message_id: int,
) -> None:
    await ensure_game_panel(bot, session, group=group)
    active_game = await active_game_for_group(session, group.id)
    await bot.send_message(
        group.telegram_chat_id,
        panel_text(active_game=active_game),
        reply_markup=panel_markup(active_game=active_game),
        reply_to_message_id=reply_to_message_id,
    )
