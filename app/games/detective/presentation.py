from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GamePlayer, GameSession
from app.db.models import Group
from app.games.detective.game import DetectivePhase
from app.games.detective.keyboards import detective_finished_keyboard, detective_round_keyboard
from app.games.enums import GameSessionStatus
from app.games.messages import upsert_phase_message
from app.games.panels import ensure_game_panel


async def detective_text(session: AsyncSession, game: GameSession) -> str:
    players = list((await session.scalars(
        select(GamePlayer).where(GamePlayer.game_id == game.id).order_by(GamePlayer.id)
    )).all())
    by_id = {player.user_telegram_id: player for player in players}
    state = dict(game.state_json or {})
    if game.status == GameSessionStatus.FINISHED.value:
        winner_id = int((game.finish_reason or "0").split(":")[-1])
        winner = by_id.get(winner_id)
        lines = [
            "🏆 ДЕТЕКТИВ · ИГРА ЗАВЕРШЕНА",
            "",
            f"Лучший детектив: {winner.display_name if winner is not None else 'игрок'}",
            f"🗂 Дел раскрыто: {game.round_no}",
            "",
            "Очки сохранены в статистике и рейтинге группы.",
        ]
        return "\n".join(lines)

    if game.phase == DetectivePhase.ROUND_RESULT.value:
        last = dict(state.get("last_case") or {})
        lines = [
            "🕵️ ДЕТЕКТИВ · РАЗБОР ДЕЛА",
            "",
            f"Дело: {last.get('title') or '—'}",
            f"Виновник: {last.get('guilty') or '—'}",
            f"Почему: {last.get('explanation') or '—'}",
            "",
            f"Обвинений: {int(last.get('answered') or 0)}",
            f"Верных: {int(last.get('correct_count') or 0)}",
            "",
            "Следующее дело откроется автоматически.",
        ]
        return "\n".join(lines)

    cases = list(state.get("cases") or [])
    index = int(state.get("case_index") or 0)
    current = dict(cases[index]) if 0 <= index < len(cases) else {}
    answered = len(list((await session.scalars(select(GamePlayer.id).where(
        GamePlayer.game_id == game.id,
        GamePlayer.status == "alive",
    ))).all()))
    lines = [
        f"🕵️ ДЕТЕКТИВ · ДЕЛО {game.round_no}",
        "",
        f"📁 {current.get('title') or 'Неизвестное дело'}",
        str(current.get("intro") or ""),
        "",
        "Изучите улики персональными кнопками, затем откройте список подозреваемых и выберите номер 1–4.",
        "Правильный ответ будет раскрыт только после завершения раунда.",
        "",
        "Счёт:",
    ]
    for player in sorted(players, key=lambda item: (-item.score, item.id)):
        if player.status == "alive":
            lines.append(f"• {player.display_name} — {player.score}")
    if answered:
        lines.extend(["", "⏱ Раунд закроется раньше, если ответят все игроки."])
    return "\n".join(lines)


async def sync_detective_ui(bot: Bot, session: AsyncSession, game: GameSession) -> None:
    game = await session.get(GameSession, game.id)
    if game is None:
        return
    group = await session.get(Group, game.group_id)
    if group is None or not group.is_active:
        return
    text = await detective_text(session, game)
    if game.status == GameSessionStatus.FINISHED.value:
        markup = detective_finished_keyboard()
    elif game.phase == DetectivePhase.INVESTIGATION.value:
        markup = detective_round_keyboard(game.id, game.phase_seq)
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
