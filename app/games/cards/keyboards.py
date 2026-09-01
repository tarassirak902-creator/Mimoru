from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def cards_turn_keyboard(game_id: int, phase_seq: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [[
        InlineKeyboardButton(text="🃏 Моя рука", callback_data=f"gm:ch:{game_id}:{phase_seq}:0"),
        InlineKeyboardButton(text="➕ Взять карту", callback_data=f"gm:cd:{game_id}:{phase_seq}"),
    ]]
    numbers = [
        InlineKeyboardButton(text=str(number), callback_data=f"gm:cp:{game_id}:{phase_seq}:{number}")
        for number in range(1, 16)
    ]
    for start in range(0, len(numbers), 5):
        rows.append(numbers[start:start + 5])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cards_finished_keyboard(game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Сыграть ещё", callback_data="gm:new:cards"),
            InlineKeyboardButton(text="🏆 Результаты", callback_data=f"gm:cgres:{game_id}"),
        ],
        [InlineKeyboardButton(text="📊 Рейтинг", callback_data="gm:rating")],
    ])
