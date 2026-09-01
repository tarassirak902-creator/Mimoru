from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GameMessage, GameSession
from app.db.models import Group
from app.games.group_limits import lobby_max_players
from app.games.manager import GameManager
from app.games.registry import GameRegistry, game_registry


log = structlog.get_logger()
_TIMED_LOBBY_GAMES = {"mafia", "spy", "quiz", "battleship", "roulette", "crocodile", "cards", "arena", "words", "detective"}


def lobby_markup(game_id: int, game_type: str) -> InlineKeyboardMarkup:
    if game_type == "mafia":
        start_callback = f"gm:ms:{game_id}"
    elif game_type == "spy":
        start_callback = f"gm:ss:{game_id}"
    elif game_type == "quiz":
        start_callback = f"gm:qs:{game_id}"
    elif game_type == "battleship":
        start_callback = f"gm:bs:{game_id}"
    elif game_type == "roulette":
        start_callback = f"gm:rs:{game_id}"
    elif game_type == "crocodile":
        start_callback = f"gm:ccs:{game_id}"
    elif game_type == "cards":
        start_callback = f"gm:cgs:{game_id}"
    elif game_type == "arena":
        start_callback = f"gm:as:{game_id}"
    elif game_type == "words":
        start_callback = f"gm:ws:{game_id}"
    elif game_type == "detective":
        start_callback = f"gm:ds:{game_id}"
    else:
        start_callback = f"gm:s:{game_id}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Присоединиться", callback_data=f"gm:j:{game_id}"), InlineKeyboardButton(text="➖ Выйти", callback_data=f"gm:l:{game_id}")],
        [InlineKeyboardButton(text="▶️ Начать", callback_data=start_callback), InlineKeyboardButton(text="❌ Отменить", callback_data=f"gm:c:{game_id}")],
    ])


async def lobby_text(session: AsyncSession, *, game: GameSession, manager: GameManager, registry: GameRegistry | None = None) -> str:
    registry = registry or game_registry
    definition = registry.require(game.game_type)
    max_players = lobby_max_players(game, definition)
    players = await manager.list_players(session, game_id=game.id)
    lines = [definition.title.upper(), "", f"👥 Игроки: {len(players)}/{max_players}", ""]
    if players:
        for index, player in enumerate(players, start=1):
            name = player.display_name or f"Игрок {player.user_telegram_id}"
            lines.append(f"{index}. {name}")
    else:
        lines.append("Пока никто не присоединился.")
    lines.extend(["", f"Минимум для старта: {definition.min_players}", "⏱ Лобби автоматически закроется через 10 минут без старта." if game.game_type in _TIMED_LOBBY_GAMES else "", "Обычная переписка группы не влияет на игру."])
    return "\n".join(line for line in lines if line != "")


async def ensure_lobby_message(bot: Bot, session: AsyncSession, *, group: Group, game: GameSession, manager: GameManager) -> int | None:
    if game.game_type in _TIMED_LOBBY_GAMES and game.deadline_at is None:
        game.deadline_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        await session.commit()
    text = await lobby_text(session, game=game, manager=manager)
    markup = lobby_markup(game.id, game.game_type)
    if game.lobby_message_id is not None:
        try:
            await bot.edit_message_text(chat_id=group.telegram_chat_id, message_id=game.lobby_message_id, text=text, reply_markup=markup)
            return game.lobby_message_id
        except TelegramBadRequest as error:
            if "message is not modified" in str(error).casefold(): return game.lobby_message_id
            log.info("game_lobby_recreate", game_id=game.id, message_id=game.lobby_message_id, error=str(error))
        except TelegramForbiddenError as error:
            log.warning("game_lobby_edit_forbidden", game_id=game.id, error=str(error)); return None
    try:
        message = await bot.send_message(group.telegram_chat_id, text, reply_markup=markup)
    except (TelegramBadRequest, TelegramForbiddenError) as error:
        log.warning("game_lobby_send_failed", game_id=game.id, error=str(error)); return None
    game.lobby_message_id = message.message_id
    session.add(GameMessage(game_id=game.id, chat_id=group.telegram_chat_id, message_id=message.message_id, kind="lobby", active=True))
    await session.commit()
    return message.message_id


async def close_lobby_message(bot: Bot, session: AsyncSession, *, group: Group, game: GameSession, text: str) -> None:
    if game.lobby_message_id is None: return
    try:
        await bot.edit_message_text(chat_id=group.telegram_chat_id, message_id=game.lobby_message_id, text=text, reply_markup=None)
    except (TelegramBadRequest, TelegramForbiddenError) as error:
        log.info("game_lobby_close_skipped", game_id=game.id, error=str(error))
    record = await session.scalar(select(GameMessage).where(GameMessage.game_id == game.id, GameMessage.message_id == game.lobby_message_id, GameMessage.active.is_(True)))
    if record is not None:
        record.active = False
        record.retired_at = datetime.now(timezone.utc)
        await session.commit()