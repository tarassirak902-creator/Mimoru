from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.games.battleship.game import BOARD_SIZE


def battleship_board_keyboard(game_id: int, phase_seq: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for row in range(BOARD_SIZE):
        buttons: list[InlineKeyboardButton] = []
        for col in range(BOARD_SIZE):
            cell = row * BOARD_SIZE + col
            buttons.append(
                InlineKeyboardButton(
                    text=f"{chr(65 + row)}{col + 1}",
                    callback_data=f"gm:bf:{game_id}:{phase_seq}:{cell}",
                )
            )
        rows.append(buttons)
    rows.append([
        InlineKeyboardButton(text="🗺 Моё поле", callback_data=f"gm:bm:{game_id}:{phase_seq}"),
        InlineKeyboardButton(text="❌ Отменить", callback_data=f"gm:bc:{game_id}:{phase_seq}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def battleship_finished_keyboard(game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Сыграть ещё", callback_data="gm:new:battleship")],
        [
            InlineKeyboardButton(text="📋 Результаты", callback_data=f"gm:bres:{game_id}"),
            InlineKeyboardButton(text="🏆 Рейтинг", callback_data="gm:rating"),
        ],
    ])
