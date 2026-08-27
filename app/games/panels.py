from __future__ import annotations

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GamePanel, GamePlayerStats, GameSession
from app.db.models import Group
from app.games.enums import ACTIVE_SESSION_STATUSES
from app.games.registry import GameRegistry, game_registry


log = structlog.get_logger()


def panel_markup(*, active_game: GameSession | None) -> InlineKeyboardMarkup:
    if active_game is not None:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👀 Открыть игру", callback_data=f"gm:open:{active_game.id}")],
            [InlineKeyboardButton(text="📖 Правила", callback_data=f"gm:rules:{active_game.game_type}")],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Начать игру", callback_data="gm:list")],
        [
            InlineKeyboardButton(text="🏆 Рейтинг", callback_data="gm:rating"),
            InlineKeyboardButton(text="👤 Мой профиль", callback_data="gm:profile"),
        ],
        [InlineKeyboardButton(text="ℹ️ Правила", callback_data="gm:rules:all")],
    ])


def panel_text(*, active_game: GameSession | None, registry: GameRegistry | None = None) -> str:
    registry = registry or game_registry
    if active_game is not None:
        definition = registry.get(active_game.game_type)
        title = definition.title if definition is not None else active_game.game_type
        return (
            "🎮 ИГРОВОЙ ЦЕНТР\n\n"
            "🔴 Сейчас идёт игра\n\n"
            f"{title}\n"
            f"🔄 Раунд: {active_game.round_no}\n\n"
            "Обычная переписка группы продолжает работать независимо от игры."
        )
    return (
        "🎮 ИГРОВОЙ ЦЕНТР\n\n"
        "🟢 Статус: свободно\n\n"
        "Здесь запускаются полноценные групповые игры Mimoru.\n"
        "Игровые действия выполняются кнопками и не мешают обычной переписке."
    )


async def active_game_for_group(session: AsyncSession, group_id: int) -> GameSession | None:
    return await session.scalar(
        select(GameSession)
        .where(
            GameSession.group_id == group_id,
            GameSession.status.in_(ACTIVE_SESSION_STATUSES),
        )
        .order_by(GameSession.id.desc())
        .limit(1)
    )


async def ensure_game_panel(
    bot: Bot,
    session: AsyncSession,
    *,
    group: Group,
    pin: bool = True,
) -> GamePanel | None:
    active_game = await active_game_for_group(session, group.id)
    text = panel_text(active_game=active_game)
    markup = panel_markup(active_game=active_game)
    panel = await session.get(GamePanel, group.id)

    if panel is not None:
        try:
            await bot.edit_message_text(
                chat_id=group.telegram_chat_id,
                message_id=panel.message_id,
                text=text,
                reply_markup=markup,
            )
            return panel
        except TelegramBadRequest as error:
            if "message is not modified" in str(error).casefold():
                return panel
            log.info(
                "game_panel_recreate",
                group_id=group.id,
                message_id=panel.message_id,
                error=str(error),
            )
        except TelegramForbiddenError as error:
            log.warning("game_panel_edit_forbidden", group_id=group.id, error=str(error))
            return None

    try:
        message = await bot.send_message(
            group.telegram_chat_id,
            text,
            reply_markup=markup,
        )
    except (TelegramBadRequest, TelegramForbiddenError) as error:
        log.warning("game_panel_send_failed", group_id=group.id, error=str(error))
        return None

    if panel is None:
        panel = GamePanel(group_id=group.id, message_id=message.message_id, pinned=False)
        session.add(panel)
    else:
        panel.message_id = message.message_id
        panel.pinned = False
    await session.commit()

    if pin:
        try:
            await bot.pin_chat_message(
                group.telegram_chat_id,
                message.message_id,
                disable_notification=True,
            )
            panel.pinned = True
            await session.commit()
        except (TelegramBadRequest, TelegramForbiddenError) as error:
            log.info("game_panel_pin_skipped", group_id=group.id, error=str(error))
    return panel


async def render_profile(session: AsyncSession, *, group_id: int, user_id: int, name: str) -> str:
    stats = await session.scalar(
        select(GamePlayerStats).where(
            GamePlayerStats.group_id == group_id,
            GamePlayerStats.user_telegram_id == user_id,
        )
    )
    if stats is None:
        return (
            f"👤 {name}\n\n"
            "🎮 Игр: 0\n🏆 Побед: 0\n⭐ Рейтинг: 1000\n🔥 Серия побед: 0"
        )
    return (
        f"👤 {name}\n\n"
        f"🎮 Игр: {stats.games_played}\n"
        f"🏆 Побед: {stats.wins}\n"
        f"⭐ Рейтинг: {stats.rating}\n"
        f"🔥 Серия побед: {stats.win_streak}"
    )


async def render_rating(session: AsyncSession, *, group_id: int) -> str:
    rows = list(
        (
            await session.scalars(
                select(GamePlayerStats)
                .where(GamePlayerStats.group_id == group_id)
                .order_by(GamePlayerStats.rating.desc(), GamePlayerStats.games_played.desc())
                .limit(10)
            )
        ).all()
    )
    if not rows:
        return "🏆 РЕЙТИНГ ИГРОКОВ\n\nРейтинговых игр в этой группе ещё не было."
    lines = ["🏆 РЕЙТИНГ ИГРОКОВ", ""]
    medals = ("🥇", "🥈", "🥉")
    for index, stats in enumerate(rows, start=1):
        prefix = medals[index - 1] if index <= 3 else f"{index}."
        lines.append(f"{prefix} ID {stats.user_telegram_id} — {stats.rating}")
    return "\n".join(lines)
