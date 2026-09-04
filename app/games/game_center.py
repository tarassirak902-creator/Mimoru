from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group
from app.games.panels import active_game_for_group, ensure_game_panel, panel_markup, panel_text
from app.games.registry import game_registry


def _games_text() -> str:
    definitions = game_registry.all()
    if not definitions:
        return (
            "🎮 ВЫБОР ИГРЫ\n\n"
            "Игровое ядро готово. Первая полноценная игра пока не подключена.\n"
            "Старые развлекательные команды сюда больше не относятся."
        )
    lines = ["🎮 ВЫБОР ИГРЫ", ""]
    for definition in definitions:
        lines.append(f"{definition.title} · {definition.min_players}–{definition.max_players} игроков")
    lines.append("\nВыберите игру кнопкой ниже.")
    return "\n".join(lines)


def _games_markup() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=definition.title, callback_data=f"gm:new:{definition.code}")
        for definition in game_registry.all()
    ]
    rows = [buttons[index:index + 2] for index in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text="◀️ В игровой центр", callback_data="gm:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def send_game_center_snapshot(
    bot: Bot,
    session: AsyncSession,
    *,
    group: Group,
    reply_to_message_id: int,
) -> None:
    """Open the game selection without creating a second bot message.

    The persistent game panel is the single visible game-center message in the
    group. If it does not exist yet, ensure_game_panel creates it once; then we
    edit that same message into the game-selection view.
    """
    panel = await ensure_game_panel(bot, session, group=group)
    if panel is None:
        return

    try:
        await bot.edit_message_text(
            chat_id=group.telegram_chat_id,
            message_id=panel.message_id,
            text=_games_text(),
            reply_markup=_games_markup(),
        )
    except TelegramBadRequest as error:
        if "message is not modified" not in str(error).casefold():
            raise
