from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def arena_keyboard(game_id: int, phase_seq: int, targets: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(text="🛡 Защита", callback_data=f"gm:ag:{game_id}:{phase_seq}"),
        InlineKeyboardButton(text="❤️ Лечение", callback_data=f"gm:ah:{game_id}:{phase_seq}"),
    ]]
    for user_id, name in targets:
        rows.append([InlineKeyboardButton(text=f"⚔️ {name[:24]}", callback_data=f"gm:aa:{game_id}:{phase_seq}:{user_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def arena_finished_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Сыграть ещё", callback_data="gm:new:arena"), InlineKeyboardButton(text="📊 Рейтинг", callback_data="gm:rating")]
    ])
