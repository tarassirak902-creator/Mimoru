from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GamePlayer, GameSession
from app.db.models import Group
from app.games.enums import GameSessionStatus
from app.games.messages import upsert_phase_message
from app.games.panels import ensure_game_panel
from app.games.words.keyboards import words_finished_keyboard, words_turn_keyboard


async def words_text(session: AsyncSession, game: GameSession) -> str:
    players = list((await session.scalars(
        select(GamePlayer).where(GamePlayer.game_id == game.id).order_by(GamePlayer.id)
    )).all())
    by_id = {player.user_telegram_id: player for player in players}
    state = dict(game.state_json or {})
    if game.status == GameSessionStatus.FINISHED.value:
        winner_id = int((game.finish_reason or "0").split(":")[-1])
        winner = by_id.get(winner_id)
        lines = [
            "🏆 СЛОВА · ИГРА ЗАВЕРШЕНА",
            "",
            f"Победитель: {winner.display_name if winner is not None else 'игрок'}",
            f"🔄 Ходов: {game.round_no}",
            "",
            "Результат сохранён в статистике и рейтинге группы.",
        ]
        return "\n".join(lines)

    turn_id = int(state.get("turn_user_id") or 0)
    turn = by_id.get(turn_id)
    current_word = str(state.get("current_word") or "—")
    required = str(state.get("required_letter") or "?").upper()
    lines = [
        "🔤 СЛОВА",
        "",
        f"Последнее слово: {current_word}",
        f"Нужная буква: {required}",
        f"👉 Ход: {turn.display_name if turn is not None else 'игрок'}",
        f"🔄 Ход №{game.round_no}",
        "",
        "Нажмите «Мои варианты», затем выберите номер 1–6.",
        "После 3 пропусков/таймаутов игрок выбывает.",
        "",
        "Игроки:",
    ]
    for player in players:
        pstate = dict(player.state_json or {})
        strikes = int(pstate.get("strikes") or 0)
        marker = "💀" if player.status == "eliminated" else "✅"
        lines.append(f"• {player.display_name} — {marker} {player.score} очк. · штрафы {strikes}/3")
    last = dict(state.get("last_action") or {})
    if last:
        actor = by_id.get(int(last.get("user_id") or 0))
        actor_name = actor.display_name if actor is not None else "Игрок"
        if last.get("type") == "pick":
            lines.extend(["", f"🔤 {actor_name}: {last.get('word')}"])
        elif last.get("type") == "skip":
            lines.extend(["", f"⏭ {actor_name} пропустил ход."])
        elif last.get("type") == "timeout":
            lines.extend(["", f"⌛ {actor_name} не успел сделать ход."])
    return "\n".join(lines)


async def sync_words_ui(bot: Bot, session: AsyncSession, game: GameSession) -> None:
    game = await session.get(GameSession, game.id)
    if game is None:
        return
    group = await session.get(Group, game.group_id)
    if group is None or not group.is_active:
        return
    text = await words_text(session, game)
    markup = words_finished_keyboard() if game.status == GameSessionStatus.FINISHED.value else words_turn_keyboard(game.id, game.phase_seq)
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
