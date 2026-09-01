from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def detective_round_keyboard(game_id: int, phase_seq: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔎 Улика 1", callback_data=f"gm:dc:{game_id}:{phase_seq}:1"),
            InlineKeyboardButton(text="🔎 Улика 2", callback_data=f"gm:dc:{game_id}:{phase_seq}:2"),
            InlineKeyboardButton(text="🔎 Улика 3", callback_data=f"gm:dc:{game_id}:{phase_seq}:3"),
        ],
        [InlineKeyboardButton(text="👥 Подозреваемые", callback_data=f"gm:dsus:{game_id}:{phase_seq}")],
        [InlineKeyboardButton(text=str(number), callback_data=f"gm:da:{game_id}:{phase_seq}:{number}") for number in range(1, 5)],
    ])


def detective_finished_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Сыграть ещё", callback_data="gm:new:detective"),
            InlineKeyboardButton(text="📊 Рейтинг", callback_data="gm:rating"),
        ]
    ])
