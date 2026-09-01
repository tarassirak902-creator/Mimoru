from __future__ import annotations

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GamePlayer, GameSession
from app.db.models import Group
from app.games.crocodile.keyboards import crocodile_finished_keyboard, crocodile_round_keyboard
from app.games.enums import GameSessionStatus
from app.games.messages import upsert_phase_message
from app.games.panels import ensure_game_panel


async def _players(session: AsyncSession, game_id: int) -> list[GamePlayer]:
    return list(
        (
            await session.scalars(
                select(GamePlayer)
                .where(GamePlayer.game_id == game_id, GamePlayer.status.in_(("alive", "eliminated")))
                .order_by(GamePlayer.score.desc(), GamePlayer.id)
            )
        ).all()
    )


async def crocodile_results_text(session: AsyncSession, game: GameSession) -> str:
    players = await _players(session, game.id)
    lines = ["📋 КРОКОДИЛ · РЕЗУЛЬТАТЫ", ""]
    for index, player in enumerate(players, start=1):
        medal = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else "•"
        lines.append(f"{medal} {player.display_name} — {player.score} очк.")
    return "\n".join(lines)


async def crocodile_public_text(session: AsyncSession, game: GameSession) -> str:
    players = await _players(session, game.id)
    state = dict(game.state_json or {})
    by_id = {player.user_telegram_id: player for player in players}

    if game.status == GameSessionStatus.FINISHED.value:
        top_score = max((player.score for player in players), default=0)
        winners = [player.display_name for player in players if player.score == top_score]
        return (
            "🏆 КРОКОДИЛ · ИГРА ЗАВЕРШЕНА\n\n"
            f"Победитель: {' / '.join(winners) if winners else '—'}\n"
            f"⭐ Лучший счёт: {top_score}\n"
            f"🎭 Раундов: {game.round_no}\n\n"
            "Результат сохранён в игровой статистике и рейтинге группы."
        )
    if game.status == GameSessionStatus.CANCELLED.value:
        return "❌ КРОКОДИЛ ОТМЕНЁН\n\nИгровая сессия закрыта."

    host_id = int(state.get("host_user_id") or 0)
    host = by_id.get(host_id)
    lines = [
        "🐊 КРОКОДИЛ",
        "",
        f"🎭 Ведущий: {host.display_name if host is not None else 'игрок'}",
        f"🔄 Раунд: {game.round_no}/{len(state.get('host_order') or [])}",
        "",
        "Ведущий показывает слово без прямого называния.",
        "Участники угадывают свободно в чате — бот не перехватывает обычные сообщения.",
        "Когда слово угадано, ведущий нажимает «Кто угадал?» и выбирает номер игрока.",
    ]
    last = dict(state.get("last_round") or {})
    if last:
        if last.get("result") == "guessed":
            guesser = by_id.get(int(last.get("guesser_user_id") or 0))
            lines.append(f"✅ Прошлое слово угадал: {guesser.display_name if guesser is not None else 'игрок'}.")
        elif last.get("result") == "timeout":
            lines.append("⌛ Прошлый раунд завершился по таймеру.")
        elif last.get("result") == "skipped":
            lines.append("⏭ Прошлое слово было пропущено.")
    return "\n".join(lines)


async def sync_crocodile_ui(bot: Bot, session: AsyncSession, game: GameSession) -> None:
    game = await session.get(GameSession, game.id)
    if game is None:
        return
    group = await session.get(Group, game.group_id)
    if group is None or not group.is_active:
        return
    text = await crocodile_public_text(session, game)
    if game.status == GameSessionStatus.FINISHED.value:
        markup = crocodile_finished_keyboard(game.id)
    elif game.status == GameSessionStatus.CANCELLED.value:
        markup = None
    else:
        active_players = await _players(session, game.id)
        markup = crocodile_round_keyboard(game.id, game.phase_seq, max(0, len(active_players) - 1))
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
