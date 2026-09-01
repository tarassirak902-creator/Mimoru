from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def words_turn_keyboard(game_id: int, phase_seq: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🧩 Мои варианты", callback_data=f"gm:wo:{game_id}:{phase_seq}"),
            InlineKeyboardButton(text="⏭ Пропустить", callback_data=f"gm:wskip:{game_id}:{phase_seq}"),
        ],
        [InlineKeyboardButton(text=str(number), callback_data=f"gm:wp:{game_id}:{phase_seq}:{number}") for number in range(1, 7)],
    ])


def words_finished_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Сыграть ещё", callback_data="gm:new:words"),
            InlineKeyboardButton(text="📊 Рейтинг", callback_data="gm:rating"),
        ]
    ])
