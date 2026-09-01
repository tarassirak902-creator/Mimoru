from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def roulette_turn_keyboard(game_id: int, phase_seq: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💣 Нажать",
                    callback_data=f"gm:rt:{game_id}:{phase_seq}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data=f"gm:rc:{game_id}:{phase_seq}",
                )
            ],
        ]
    )


def roulette_finished_keyboard(game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Сыграть ещё",
                    callback_data="gm:new:roulette",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Результаты",
                    callback_data=f"gm:rres:{game_id}",
                ),
                InlineKeyboardButton(
                    text="🏆 Рейтинг",
                    callback_data="gm:rating",
                ),
            ],
        ]
    )
