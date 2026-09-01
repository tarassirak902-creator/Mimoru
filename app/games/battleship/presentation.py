from __future__ import annotations

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GamePlayer, GameSession
from app.db.models import Group
from app.games.battleship.game import BOARD_SIZE, BattleshipPhase
from app.games.battleship.keyboards import battleship_board_keyboard, battleship_finished_keyboard
from app.games.enums import GameSessionStatus
from app.games.messages import upsert_phase_message
from app.games.panels import ensure_game_panel


def _grid_text(board: dict) -> str:
    ships = set(board.get("ships") or [])
    hits = set(board.get("hits") or [])
    misses = set(board.get("misses") or [])
    rows = ["   1 2 3 4 5"]
    for row in range(BOARD_SIZE):
        cells: list[str] = []
        for col in range(BOARD_SIZE):
            cell = row * BOARD_SIZE + col
            if cell in hits:
                mark = "💥"
            elif cell in misses:
                mark = "•"
            elif cell in ships:
                mark = "🚢"
            else:
                mark = "▫️"
            cells.append(mark)
        rows.append(f"{chr(65 + row)} " + " ".join(cells))
    return "\n".join(rows)


async def battleship_private_board_text(session: AsyncSession, game: GameSession, user_id: int) -> str:
    state = dict(game.state_json or {})
    board = dict((state.get("boards") or {}).get(str(user_id)) or {})
    return "🚢 Ваше поле\n\n" + _grid_text(board)


async def battleship_results_text(session: AsyncSession, game: GameSession) -> str:
    players = list((await session.scalars(
        select(GamePlayer).where(GamePlayer.game_id == game.id).order_by(GamePlayer.id)
    )).all())
    winner_id = None
    if game.finish_reason and game.finish_reason.startswith("winner:"):
        try:
            winner_id = int(game.finish_reason.split(":", 1)[1])
        except ValueError:
            winner_id = None
    lines = ["📋 МОРСКОЙ БОЙ · РЕЗУЛЬТАТЫ", ""]
    for player in players:
        mark = "🏆" if player.user_telegram_id == winner_id else "•"
        lines.append(f"{mark} {player.display_name}")
    lines.extend(["", f"Ходов: {game.round_no}"])
    return "\n".join(lines)


async def battleship_public_text(session: AsyncSession, game: GameSession) -> str:
    players = list((await session.scalars(
        select(GamePlayer).where(GamePlayer.game_id == game.id).order_by(GamePlayer.id)
    )).all())
    names = {player.user_telegram_id: player.display_name for player in players}
    state = dict(game.state_json or {})
    if game.status == GameSessionStatus.FINISHED.value:
        winner_id = None
        if game.finish_reason and game.finish_reason.startswith("winner:"):
            try:
                winner_id = int(game.finish_reason.split(":", 1)[1])
            except ValueError:
                pass
        return (
            "🏆 МОРСКОЙ БОЙ · ИГРА ЗАВЕРШЕНА\n\n"
            f"Победитель: {names.get(winner_id, 'неизвестно')}\n"
            f"Ходов: {game.round_no}\n\n"
            "Результат сохранён в игровой статистике и рейтинге группы."
        )
    if game.status == GameSessionStatus.CANCELLED.value:
        return "❌ МОРСКОЙ БОЙ ОТМЕНЁН\n\nИгровая сессия закрыта."
    turn_user_id = state.get("turn_user_id")
    last = dict(state.get("last_shot") or {})
    lines = [
        "🚢 МОРСКОЙ БОЙ",
        "",
        f"Ход: {names.get(turn_user_id, 'неизвестно')}",
        "Нажмите координату для выстрела. Бот проверит право хода персонально.",
        "",
    ]
    if last.get("result") == "hit":
        lines.append(f"💥 Последний выстрел: {last.get('coord')} — попадание")
    elif last.get("result") == "miss":
        lines.append(f"🌊 Последний выстрел: {last.get('coord')} — мимо")
    elif last.get("result") == "timeout":
        lines.append("⏱ Предыдущий игрок пропустил ход по таймауту.")
    return "\n".join(lines)


async def sync_battleship_ui(bot: Bot, session: AsyncSession, game: GameSession) -> None:
    game = await session.get(GameSession, game.id)
    if game is None:
        return
    group = await session.get(Group, game.group_id)
    if group is None or not group.is_active:
        return
    text = await battleship_public_text(session, game)
    if game.status == GameSessionStatus.FINISHED.value:
        markup = battleship_finished_keyboard(game.id)
    elif game.status == GameSessionStatus.CANCELLED.value:
        markup = None
    elif game.phase == BattleshipPhase.TURN.value:
        markup = battleship_board_keyboard(game.id, game.phase_seq)
    else:
        markup = None
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
