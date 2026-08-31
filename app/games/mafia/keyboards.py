from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def mafia_action_keyboard(*, game_id: int, phase_seq: int, target_count: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [[
        InlineKeyboardButton(
            text="🎭 Моя роль",
            callback_data=f"gm:mr:{game_id}:{phase_seq}",
        )
    ]]
    numbers = list(range(1, target_count + 1))
    if numbers:
        map_buttons = [
            InlineKeyboardButton(
                text=f"👁 1–{min(7, target_count)}",
                callback_data=f"gm:mm:{game_id}:{phase_seq}:1",
            )
        ]
        if target_count > 7:
            map_buttons.append(
                InlineKeyboardButton(
                    text=f"👁 8–{target_count}",
                    callback_data=f"gm:mm:{game_id}:{phase_seq}:2",
                )
            )
        rows.append(map_buttons)
        for offset in range(0, len(numbers), 5):
            rows.append([
                InlineKeyboardButton(
                    text=str(number),
                    callback_data=f"gm:ma:{game_id}:{phase_seq}:{number}",
                )
                for number in numbers[offset:offset + 5]
            ])
    rows.append([
        InlineKeyboardButton(
            text="❌ Отменить игру",
            callback_data=f"gm:mc:{game_id}:{phase_seq}",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)
