from __future__ import annotations

from aiogram import Bot
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GameAction, GamePlayer, GameSession
from app.db.models import Group
from app.games.enums import GameSessionStatus
from app.games.messages import upsert_phase_message
from app.games.panels import ensure_game_panel
from app.games.quiz.game import QuizPhase
from app.games.quiz.keyboards import quiz_action_keyboard, quiz_finished_keyboard


async def _players(session: AsyncSession, game_id: int) -> list[GamePlayer]:
    return list((await session.scalars(
        select(GamePlayer).where(GamePlayer.game_id == game_id).order_by(GamePlayer.score.desc(), GamePlayer.id)
    )).all())


async def _answer_count(session: AsyncSession, game: GameSession) -> int:
    return int(await session.scalar(
        select(func.count(GameAction.id)).where(
            GameAction.game_id == game.id,
            GameAction.phase_seq == game.phase_seq,
            GameAction.action_type == "quiz_answer",
        )
    ) or 0)


async def quiz_results_text(session: AsyncSession, game: GameSession) -> str:
    players = await _players(session, game.id)
    lines = ["📋 КВИЗ · РЕЗУЛЬТАТЫ", ""]
    for index, player in enumerate(players, start=1):
        lines.append(f"{index}. {player.display_name} — {player.score} очк.")
    return "\n".join(lines)


async def quiz_public_text(session: AsyncSession, game: GameSession) -> str:
    state = dict(game.state_json or {})
    players = await _players(session, game.id)
    if game.status == GameSessionStatus.FINISHED.value:
        top_score = max((player.score for player in players), default=0)
        winners = [player.display_name for player in players if player.score == top_score]
        return "\n".join([
            "🏆 КВИЗ · ИГРА ЗАВЕРШЕНА",
            "",
            f"Победитель: {', '.join(winners) if winners else 'нет'}",
            f"⭐ Лучший результат: {top_score}",
            f"🧠 Вопросов: {game.round_no}",
            "",
            "Результат сохранён в игровой статистике и рейтинге группы.",
        ])
    if game.status == GameSessionStatus.CANCELLED.value:
        return "❌ КВИЗ ОТМЕНЁН\n\nИгровая сессия закрыта."

    rounds = list(state.get("rounds") or [])
    index = int(state.get("round_index") or 0)
    if game.phase == QuizPhase.QUESTION.value and 0 <= index < len(rounds):
        current = dict(rounds[index])
        options = list(current.get("options") or [])
        lines = [
            f"🧠 КВИЗ · ВОПРОС {game.round_no}/{len(rounds)}",
            "",
            str(current.get("question") or "Вопрос недоступен"),
            "",
        ]
        for number, option in enumerate(options, start=1):
            lines.append(f"{chr(64 + number)}. {option}")
        lines.extend([
            "",
            f"✅ Ответили: {await _answer_count(session, game)}/{len(players)}",
            "Выберите вариант кнопкой ниже.",
        ])
        return "\n".join(lines)

    last_round = dict(state.get("last_round") or {})
    if game.phase == QuizPhase.ROUND_RESULT.value:
        return "\n".join([
            f"🧠 КВИЗ · ИТОГ ВОПРОСА {last_round.get('round_no', game.round_no)}",
            "",
            f"✅ Правильный ответ: {last_round.get('correct_answer', 'неизвестно')}",
            f"🎯 Правильно ответили: {last_round.get('correct_count', 0)}",
            f"👥 Всего ответили: {last_round.get('answered', 0)}/{len(players)}",
            "",
            "Следующий вопрос появится автоматически.",
        ])
    return "🧠 КВИЗ\n\nИгра восстанавливается."


async def sync_quiz_ui(bot: Bot, session: AsyncSession, game: GameSession) -> None:
    game = await session.get(GameSession, game.id)
    if game is None:
        return
    group = await session.get(Group, game.group_id)
    if group is None or not group.is_active:
        return
    text = await quiz_public_text(session, game)
    if game.status == GameSessionStatus.FINISHED.value:
        markup = quiz_finished_keyboard(game.id)
    elif game.status == GameSessionStatus.CANCELLED.value:
        markup = None
    else:
        state = dict(game.state_json or {})
        rounds = list(state.get("rounds") or [])
        index = int(state.get("round_index") or 0)
        option_count = 0
        if 0 <= index < len(rounds):
            option_count = len(list(dict(rounds[index]).get("options") or []))
        markup = quiz_action_keyboard(
            game_id=game.id,
            phase_seq=game.phase_seq,
            phase=game.phase,
            option_count=option_count,
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
