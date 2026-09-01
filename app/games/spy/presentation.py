from __future__ import annotations

from aiogram import Bot
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GameAction, GamePlayer, GameSession
from app.db.models import Group
from app.games.enums import GameSessionStatus
from app.games.messages import upsert_phase_message
from app.games.panels import ensure_game_panel
from app.games.spy.game import SpyPhase
from app.games.spy.keyboards import spy_action_keyboard, spy_finished_keyboard


async def _player_count(session: AsyncSession, game_id: int) -> int:
    return int(await session.scalar(select(func.count(GamePlayer.id)).where(GamePlayer.game_id == game_id)) or 0)


async def _vote_count(session: AsyncSession, game: GameSession) -> int:
    return int(await session.scalar(
        select(func.count(GameAction.id)).where(
            GameAction.game_id == game.id,
            GameAction.phase_seq == game.phase_seq,
            GameAction.action_type == "spy_vote",
        )
    ) or 0)


async def spy_results_text(session: AsyncSession, game: GameSession) -> str:
    players = list((await session.scalars(
        select(GamePlayer).where(GamePlayer.game_id == game.id).order_by(GamePlayer.id)
    )).all())
    state = dict(game.state_json or {})
    lines = [
        "📋 ШПИОН · РЕЗУЛЬТАТЫ",
        "",
        f"📍 Локация: {state.get('location', 'неизвестно')}",
        "",
    ]
    for player in players:
        role = "🕵️ Шпион" if player.role == "spy" else "👥 Местный"
        lines.append(f"• {player.display_name} — {role}")
    return "\n".join(lines)


async def spy_public_text(session: AsyncSession, game: GameSession) -> str:
    state = dict(game.state_json or {})
    player_count = await _player_count(session, game.id)
    if game.status == GameSessionStatus.FINISHED.value:
        winner = "🕵️ Шпион" if game.finish_reason == "winner:spy" else "👥 Местные"
        vote = dict(state.get("last_vote") or {})
        lines = [
            "🏆 ШПИОН · ИГРА ЗАВЕРШЕНА",
            "",
            f"Победили: {winner}",
            f"📍 Локация: {state.get('location', 'неизвестно')}",
        ]
        if vote.get("tie"):
            lines.append("🗳 Голоса разделились — Шпион избежал разоблачения.")
        lines.extend(["", "Результат сохранён в игровой статистике и рейтинге группы."])
        return "\n".join(lines)
    if game.status == GameSessionStatus.CANCELLED.value:
        return "❌ ШПИОН ОТМЕНЁН\n\nИгровая сессия закрыта."

    lines = ["🕵️ ШПИОН", "", f"👥 Игроков: {player_count}", ""]
    if game.phase == SpyPhase.DISCUSSION.value:
        lines.extend([
            "💬 ОБСУЖДЕНИЕ",
            "Откройте «Моя роль». Все, кроме Шпиона, увидят общую локацию.",
            "Обсуждайте и задавайте вопросы обычными сообщениями — бот их не считает игровыми командами.",
        ])
    elif game.phase == SpyPhase.VOTING.value:
        lines.extend([
            "🗳 ГОЛОСОВАНИЕ",
            f"Проголосовало: {await _vote_count(session, game)}/{player_count}",
            "Откройте персональный список и нажмите номер подозреваемого.",
        ])
    elif game.phase == SpyPhase.SPY_GUESS.value:
        lines.extend([
            "🎯 ШПИОН НАЙДЕН",
            "У Шпиона есть последняя попытка угадать локацию.",
            "Только Шпион может использовать кнопки выбора места.",
        ])
    return "\n".join(lines)


async def sync_spy_ui(bot: Bot, session: AsyncSession, game: GameSession) -> None:
    game = await session.get(GameSession, game.id)
    if game is None:
        return
    group = await session.get(Group, game.group_id)
    if group is None or not group.is_active:
        return
    text = await spy_public_text(session, game)
    if game.status in {GameSessionStatus.FINISHED.value, GameSessionStatus.CANCELLED.value}:
        markup = spy_finished_keyboard(game.id) if game.status == GameSessionStatus.FINISHED.value else None
    else:
        state = dict(game.state_json or {})
        markup = spy_action_keyboard(
            game_id=game.id,
            phase_seq=game.phase_seq,
            phase=game.phase,
            player_count=await _player_count(session, game.id),
            location_count=len(list(state.get("location_options") or [])),
        )
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
