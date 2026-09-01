from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.games.quiz.game import QuizPhase


def quiz_action_keyboard(*, game_id: int, phase_seq: int, phase: str, option_count: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if phase == QuizPhase.QUESTION.value:
        buttons = [
            InlineKeyboardButton(
                text=f"{chr(64 + number)}",
                callback_data=f"gm:qa:{game_id}:{phase_seq}:{number}",
            )
            for number in range(1, option_count + 1)
        ]
        rows.extend([buttons[index:index + 2] for index in range(0, len(buttons), 2)])
    rows.append([
        InlineKeyboardButton(
            text="❌ Отменить",
            callback_data=f"gm:qc:{game_id}:{phase_seq}",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def quiz_finished_keyboard(game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Сыграть ещё", callback_data="gm:new:quiz")],
        [
            InlineKeyboardButton(text="📋 Результаты", callback_data=f"gm:qres:{game_id}"),
            InlineKeyboardButton(text="🏆 Рейтинг", callback_data="gm:rating"),
        ],
    ])
