from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def crocodile_round_keyboard(game_id: int, phase_seq: int, target_count: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="🎭 Моё слово",
                callback_data=f"gm:cw:{game_id}:{phase_seq}",
            ),
            InlineKeyboardButton(
                text="👥 Кто угадал?",
                callback_data=f"gm:cl:{game_id}:{phase_seq}",
            ),
        ]
    ]
    numbers = [
        InlineKeyboardButton(text=str(number), callback_data=f"gm:ct:{game_id}:{phase_seq}:{number}")
        for number in range(1, target_count + 1)
    ]
    for start in range(0, len(numbers), 5):
        rows.append(numbers[start:start + 5])
    rows.append([
        InlineKeyboardButton(
            text="⏭ Пропустить",
            callback_data=f"gm:ck:{game_id}:{phase_seq}",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def crocodile_finished_keyboard(game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Сыграть ещё", callback_data="gm:new:crocodile"),
                InlineKeyboardButton(text="🏆 Результаты", callback_data=f"gm:cres:{game_id}"),
            ],
            [InlineKeyboardButton(text="📊 Рейтинг", callback_data="gm:rating")],
        ]
    )
