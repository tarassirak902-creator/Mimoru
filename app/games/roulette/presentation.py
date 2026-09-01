from __future__ import annotations

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GamePlayer, GameSession
from app.db.models import Group
from app.games.enums import GameSessionStatus
from app.games.messages import upsert_phase_message
from app.games.panels import ensure_game_panel
from app.games.roulette.keyboards import roulette_finished_keyboard, roulette_turn_keyboard


async def _players(session: AsyncSession, game_id: int) -> list[GamePlayer]:
    return list(
        (
            await session.scalars(
                select(GamePlayer).where(GamePlayer.game_id == game_id).order_by(GamePlayer.id)
            )
        ).all()
    )


async def roulette_results_text(session: AsyncSession, game: GameSession) -> str:
    players = await _players(session, game.id)
    winner_id = None
    if game.finish_reason and game.finish_reason.startswith("winner:"):
        try:
            winner_id = int(game.finish_reason.split(":", 1)[1])
        except ValueError:
            winner_id = None
    lines = ["📋 РУЛЕТКА · РЕЗУЛЬТАТЫ", ""]
    for player in players:
        if player.user_telegram_id == winner_id:
            status = "🏆 победитель"
        elif player.status == "eliminated":
            status = "💥 выбыл"
        else:
            status = "✅ выжил"
        lines.append(f"• {player.display_name} — {status}")
    return "\n".join(lines)


async def roulette_public_text(session: AsyncSession, game: GameSession) -> str:
    players = await _players(session, game.id)
    state = dict(game.state_json or {})
    by_id = {player.user_telegram_id: player for player in players}

    if game.status == GameSessionStatus.FINISHED.value:
        winner_id = int(state.get("turn_user_id") or 0)
        winner = by_id.get(winner_id)
        winner_name = winner.display_name if winner is not None else "Игрок"
        return (
            "🏆 РУЛЕТКА · ИГРА ЗАВЕРШЕНА\n\n"
            f"Победитель: 🏆 {winner_name}\n"
            f"🎮 Ходов: {game.round_no}\n\n"
            "Результат сохранён в игровой статистике и рейтинге группы."
        )
    if game.status == GameSessionStatus.CANCELLED.value:
        return "❌ РУЛЕТКА ОТМЕНЕНА\n\nИгровая сессия закрыта."

    alive_ids = [int(user_id) for user_id in list(state.get("alive_user_ids") or [])]
    current_id = int(state.get("turn_user_id") or 0)
    current = by_id.get(current_id)
    lines = [
        "💣 РУЛЕТКА",
        "",
        f"👥 В игре: {len(alive_ids)}/{len(players)}",
        f"🎯 Ход: {current.display_name if current is not None else 'игрока'}",
    ]
    last = dict(state.get("last_turn") or {})
    if last:
        actor = by_id.get(int(last.get("actor_user_id") or 0))
        actor_name = actor.display_name if actor is not None else "Игрок"
        if last.get("result") == "fired":
            lines.append(f"💥 {actor_name} выбыл.")
        elif last.get("result") == "safe":
            lines.append(f"😮‍💨 {actor_name}: пусто.")
    lines.extend(
        [
            "",
            "В барабане один патрон. Позиция фиксируется сервером и не меняется от повторных нажатий.",
            "Нажать кнопку может только игрок, чей сейчас ход.",
        ]
    )
    return "\n".join(lines)


async def sync_roulette_ui(bot: Bot, session: AsyncSession, game: GameSession) -> None:
    game = await session.get(GameSession, game.id)
    if game is None:
        return
    group = await session.get(Group, game.group_id)
    if group is None or not group.is_active:
        return
    text = await roulette_public_text(session, game)
    if game.status == GameSessionStatus.FINISHED.value:
        markup = roulette_finished_keyboard(game.id)
    elif game.status == GameSessionStatus.CANCELLED.value:
        markup = None
    else:
        markup = roulette_turn_keyboard(game.id, game.phase_seq)
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
