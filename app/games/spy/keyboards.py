from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.games.spy.game import SpyPhase


def _number_rows(
    prefix: str,
    count: int,
    *,
    per_row: int = 4,
) -> list[list[InlineKeyboardButton]]:
    buttons = [
        InlineKeyboardButton(
            text=str(number),
            callback_data=f"{prefix}:{number}",
        )
        for number in range(1, count + 1)
    ]
    return [
        buttons[index : index + per_row]
        for index in range(0, len(buttons), per_row)
    ]


def spy_action_keyboard(
    *,
    game_id: int,
    phase_seq: int,
    phase: str,
    player_count: int,
    location_count: int,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="🎭 Моя роль",
                callback_data=f"gm:sr:{game_id}:{phase_seq}",
            )
        ]
    ]
    if phase == SpyPhase.VOTING.value:
        rows.append(
            [
                InlineKeyboardButton(
                    text="👁 Мой список",
                    callback_data=f"gm:svm:{game_id}:{phase_seq}",
                )
            ]
        )
        rows.extend(
            _number_rows(
                f"gm:sv:{game_id}:{phase_seq}",
                max(0, player_count - 1),
            )
        )
    elif phase == SpyPhase.SPY_GUESS.value:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🗺 Варианты мест",
                    callback_data=f"gm:slm:{game_id}:{phase_seq}",
                )
            ]
        )
        rows.extend(
            _number_rows(
                f"gm:sl:{game_id}:{phase_seq}",
                location_count,
            )
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="❌ Отменить",
                callback_data=f"gm:sc:{game_id}:{phase_seq}",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def spy_finished_keyboard(game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Сыграть ещё",
                    callback_data="gm:new:spy",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Результаты",
                    callback_data=f"gm:sres:{game_id}",
                ),
                InlineKeyboardButton(
                    text="🏆 Рейтинг",
                    callback_data="gm:rating",
                ),
            ],
        ]
    )
