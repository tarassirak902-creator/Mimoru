from __future__ import annotations

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GamePlayer, GameSession
from app.db.models import Group
from app.games.cards.game import card_label
from app.games.cards.keyboards import cards_finished_keyboard, cards_turn_keyboard
from app.games.enums import GameSessionStatus
from app.games.messages import upsert_phase_message
from app.games.panels import ensure_game_panel


async def _players(session: AsyncSession, game_id: int) -> list[GamePlayer]:
    return list((await session.scalars(
        select(GamePlayer)
        .where(GamePlayer.game_id == game_id, GamePlayer.status == "alive")
        .order_by(GamePlayer.id)
    )).all())


async def cards_public_text(session: AsyncSession, game: GameSession) -> str:
    players = await _players(session, game.id)
    state = dict(game.state_json or {})
    by_id = {player.user_telegram_id: player for player in players}
    if game.status == GameSessionStatus.FINISHED.value:
        winner_id = int((game.finish_reason or "0").split(":")[-1]) if game.finish_reason else 0
        winner = by_id.get(winner_id)
        return (
            "🏆 КАРТЫ · ИГРА ЗАВЕРШЕНА\n\n"
            f"Победитель: {winner.display_name if winner is not None else 'игрок'}\n"
            f"🔄 Ходов: {game.round_no}\n\n"
            "Результат сохранён в игровой статистике и рейтинге группы."
        )
    if game.status == GameSessionStatus.CANCELLED.value:
        return "❌ КАРТОЧНАЯ ИГРА ОТМЕНЕНА\n\nИгровая сессия закрыта."
    turn_id = int(state.get("turn_user_id") or 0)
    turn = by_id.get(turn_id)
    discard = list(state.get("discard") or [])
    top = discard[-1] if discard else "R:1"
    hands = dict(state.get("hands") or {})
    lines = [
        "🃏 КАРТЫ",
        "",
        f"🎴 Верхняя карта: {card_label(top)}",
        f"👉 Ход: {turn.display_name if turn is not None else 'игрок'}",
        f"🔄 Ход №{game.round_no}",
        "",
        "Карту можно положить по совпадению цвета или значения.",
        "⛔ пропускает следующего, 🔄 меняет направление, +2 заставляет следующего взять две карты.",
        "",
        "Карт на руках:",
    ]
    for player in players:
        lines.append(f"• {player.display_name} — {len(list(hands.get(str(player.user_telegram_id)) or []))}")
    last = dict(state.get("last_action") or {})
    if last:
        actor = by_id.get(int(last.get("user_id") or 0))
        if last.get("type") == "play" and last.get("card"):
            lines.extend(["", f"Последний ход: {actor.display_name if actor else 'игрок'} сыграл {card_label(str(last['card']))}."])
        elif last.get("type") == "draw":
            lines.extend(["", f"Последний ход: {actor.display_name if actor else 'игрок'} взял карту."])
        elif last.get("type") == "timeout":
            lines.extend(["", f"⌛ {actor.display_name if actor else 'игрок'} не успел — карта взята автоматически."])
    return "\n".join(lines)


async def cards_results_text(session: AsyncSession, game: GameSession) -> str:
    players = await _players(session, game.id)
    state = dict(game.state_json or {})
    hands = dict(state.get("hands") or {})
    lines = ["📋 КАРТЫ · РЕЗУЛЬТАТЫ", ""]
    for player in sorted(players, key=lambda item: (len(list(hands.get(str(item.user_telegram_id)) or [])), -item.score)):
        lines.append(f"• {player.display_name} — карт: {len(list(hands.get(str(player.user_telegram_id)) or []))}, сыграно: {player.score}")
    return "\n".join(lines)


async def sync_cards_ui(bot: Bot, session: AsyncSession, game: GameSession) -> None:
    game = await session.get(GameSession, game.id)
    if game is None:
        return
    group = await session.get(Group, game.group_id)
    if group is None or not group.is_active:
        return
    text = await cards_public_text(session, game)
    if game.status == GameSessionStatus.FINISHED.value:
        markup = cards_finished_keyboard(game.id)
    elif game.status == GameSessionStatus.CANCELLED.value:
        markup = None
    else:
        markup = cards_turn_keyboard(game.id, game.phase_seq)
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
