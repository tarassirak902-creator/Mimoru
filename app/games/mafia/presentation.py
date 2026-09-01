from __future__ import annotations

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GameAction, GamePlayer, GameSession
from app.db.models import Group
from app.games.enums import GameSessionStatus
from app.games.mafia.game import MafiaPhase
from app.games.mafia.keyboards import mafia_action_keyboard
from app.games.messages import upsert_phase_message
from app.games.panels import ensure_game_panel


PHASE_TITLES = {
    MafiaPhase.DAY_START.value: "☀️ НАСТУПАЕТ ДЕНЬ",
    MafiaPhase.DISCUSSION.value: "💬 ОБСУЖДЕНИЕ",
    MafiaPhase.DAY_VOTING.value: "🗳 ГОЛОСОВАНИЕ",
    MafiaPhase.VOTING_RESULT.value: "⚖️ ИТОГ ГОЛОСОВАНИЯ",
    MafiaPhase.NIGHT_START.value: "🌙 НАСТУПАЕТ НОЧЬ",
    MafiaPhase.NIGHT_ACTIONS.value: "🌙 НОЧНЫЕ ДЕЙСТВИЯ",
    MafiaPhase.NIGHT_RESULT.value: "🌅 ИТОГ НОЧИ",
}
ROLE_LABELS = {
    "civilian": "👨 Мирный",
    "mafia": "🔪 Мафия",
    "doctor": "🩺 Доктор",
    "commissioner": "🕵️ Комиссар",
}


async def _alive_count(session: AsyncSession, game_id: int) -> int:
    value = await session.scalar(
        select(func.count(GamePlayer.id)).where(
            GamePlayer.game_id == game_id,
            GamePlayer.status == "alive",
        )
    )
    return int(value or 0)


async def _action_count(session: AsyncSession, game: GameSession) -> int:
    value = await session.scalar(
        select(func.count(GameAction.id)).where(
            GameAction.game_id == game.id,
            GameAction.phase_seq == game.phase_seq,
        )
    )
    return int(value or 0)


def _day_result_text(state: dict) -> str:
    result = state.get("last_day_result") or {}
    if result.get("executed_name"):
        return f"Группа выбрала: {result['executed_name']} покидает игру."
    if result.get("tie"):
        return "Голоса разделились. Сегодня никто не покидает игру."
    return "Голосование завершено без казни."


def _night_result_text(state: dict) -> str:
    result = state.get("last_night_result") or {}
    if result.get("saved"):
        return "Ночью было совершено нападение, но жертву удалось спасти."
    if result.get("killed_name"):
        return f"Этой ночью погибает {result['killed_name']}."
    return "Ночь прошла без жертв."


def _afk_text(state: dict) -> str | None:
    removed = state.get("last_afk_removed") or []
    if not removed:
        return None
    return "⌛ За повторное бездействие игру покидают: " + ", ".join(removed) + "."


def _finish_event_lines(state: dict) -> list[str]:
    context = state.get("finish_context") or {}
    phase = context.get("phase")
    lines: list[str] = []
    if phase == MafiaPhase.DAY_VOTING.value:
        lines.append(_day_result_text(state))
    elif phase == MafiaPhase.NIGHT_ACTIONS.value:
        lines.append(_night_result_text(state))
    afk = _afk_text(state)
    if afk:
        lines.append(afk)
    return lines


async def mafia_results_text(session: AsyncSession, game: GameSession) -> str:
    players = list((await session.scalars(
        select(GamePlayer)
        .where(GamePlayer.game_id == game.id, GamePlayer.role.is_not(None))
        .order_by(GamePlayer.id)
    )).all())
    lines = ["📋 МАФИЯ · РЕЗУЛЬТАТЫ", ""]
    for player in players:
        status = "✅" if player.status == "alive" else "💀"
        lines.append(f"{status} {player.display_name} — {ROLE_LABELS.get(player.role or '', 'роль неизвестна')}")
    return "\n".join(lines)


async def mafia_public_text(session: AsyncSession, game: GameSession) -> str:
    alive = await _alive_count(session, game.id)
    state = dict(game.state_json or {})
    if game.status == GameSessionStatus.FINISHED.value:
        winner = "🔪 Мафия" if game.finish_reason == "winner:mafia" else "🏘 Мирные жители"
        lines = [
            "🏆 МАФИЯ · ИГРА ЗАВЕРШЕНА",
            "",
        ]
        lines.extend(_finish_event_lines(state))
        if len(lines) > 2:
            lines.append("")
        lines.extend([
            f"Победила команда: {winner}",
            f"🎮 Раундов: {game.round_no}",
            "",
            "Результат сохранён в профилях и рейтинге группы.",
        ])
        return "\n".join(lines)
    if game.status == GameSessionStatus.CANCELLED.value:
        return "❌ МАФИЯ ОТМЕНЕНА\n\nИгровая сессия закрыта. Группа снова свободна для новой игры."
    title = PHASE_TITLES.get(game.phase, "🐺 МАФИЯ")
    lines = [
        "🐺 МАФИЯ",
        "",
        title,
        f"🔄 День: {state.get('day', game.round_no or 1)}",
        f"👥 Живых: {alive}",
        "",
    ]
    if game.phase == MafiaPhase.DAY_START.value:
        lines.append("Проверьте свою роль кнопкой ниже. Скоро начнётся обсуждение.")
    elif game.phase == MafiaPhase.DISCUSSION.value:
        lines.append("Обсуждайте подозрения обычными сообщениями. Бот не воспринимает переписку как команды.")
    elif game.phase == MafiaPhase.DAY_VOTING.value:
        lines.append(f"Проголосовало: {await _action_count(session, game)}/{alive}")
        lines.append("Откройте свой список и нажмите номер игрока, которого хотите исключить.")
    elif game.phase == MafiaPhase.VOTING_RESULT.value:
        lines.append(_day_result_text(state))
        afk = _afk_text(state)
        if afk:
            lines.append(afk)
    elif game.phase == MafiaPhase.NIGHT_START.value:
        lines.append("Город засыпает. Ночные роли готовятся сделать выбор.")
    elif game.phase == MafiaPhase.NIGHT_ACTIONS.value:
        lines.append("Ночные роли: откройте персональный список и нажмите номер цели. Остальные просто ждут.")
    elif game.phase == MafiaPhase.NIGHT_RESULT.value:
        lines.append(_night_result_text(state))
        afk = _afk_text(state)
        if afk:
            lines.append(afk)
    return "\n".join(lines)


def finished_markup(game: GameSession) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="🔄 Сыграть ещё", callback_data="gm:new:mafia")]]
    if game.status == GameSessionStatus.FINISHED.value:
        rows.append([InlineKeyboardButton(text="📋 Результаты", callback_data=f"gm:mres:{game.id}")])
    rows.append([InlineKeyboardButton(text="🏆 Рейтинг", callback_data="gm:rating")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def sync_mafia_ui(bot: Bot, session: AsyncSession, game: GameSession) -> None:
    game = await session.get(GameSession, game.id)
    if game is None:
        return
    group = await session.get(Group, game.group_id)
    if group is None or not group.is_active:
        return
    alive = await _alive_count(session, game.id)
    text = await mafia_public_text(session, game)
    if game.status in {GameSessionStatus.FINISHED.value, GameSessionStatus.CANCELLED.value}:
        markup = finished_markup(game)
    else:
        target_count = alive if game.phase in {MafiaPhase.DAY_VOTING.value, MafiaPhase.NIGHT_ACTIONS.value} else 0
        markup = mafia_action_keyboard(game_id=game.id, phase_seq=game.phase_seq, target_count=target_count)
    await upsert_phase_message(
        bot,
        session,
        game_id=game.id,
        chat_id=group.telegram_chat_id,
        text=text,
        reply_markup=markup,
        kind="phase",
    )
    await ensure_game_panel(bot, session, group=group, pin=False)
