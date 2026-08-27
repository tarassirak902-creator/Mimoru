from __future__ import annotations

import math

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.entertainment_contracts import ENTERTAINMENT_ACTIONS, RELATIONSHIP_ACTIONS
from app.game_contracts import PROPOSALS


router = Router(name=__name__)
GROUP_TYPES = {"group", "supergroup"}
OPEN_WORDS = {"развлечения", "развлекательные команды"}
FOREIGN_BUTTON_NOTICE = "Не для тебя мать кнопки прислала, отдыхай! Выпей лучше валерьянки и узбогойся..."
PAGE_SIZE = 18


def _main_text() -> str:
    return (
        "🎭 Mimoru · Развлечения\n\n"
        "Здесь находятся только развлекательные команды. Это не игры: у них нет побед, очков или игровой статистики.\n\n"
        "🎭 Действия — обнять, поцеловать, ударить, дать дошик, покормить и другие шуточные reply-команды.\n"
        "💞 Семья и отношения — предложение, брак, развод, ссоры и примирения.\n\n"
        "Для настоящих игр используйте /games."
    )


def _all_actions() -> list[str]:
    return sorted(ENTERTAINMENT_ACTIONS, key=str.casefold)


def _family_actions() -> list[str]:
    return sorted(set(RELATIONSHIP_ACTIONS) | set(PROPOSALS) | {"развестись", "подать на развод", "мой брак", "мои отношения"}, key=str.casefold)


def _page_text(page: int) -> str:
    actions = _all_actions()
    pages = max(1, math.ceil(len(actions) / PAGE_SIZE))
    page = max(0, min(page, pages - 1))
    start = page * PAGE_SIZE
    lines = "\n".join(f"• {action}" for action in actions[start:start + PAGE_SIZE])
    return (
        "🎭 Развлекательные действия\n\n"
        "Ответьте на сообщение участника одной из команд:\n\n"
        f"{lines}\n\nСтраница {page + 1} из {pages} · Всего: {len(actions)}"
    )


def _family_text() -> str:
    lines = "\n".join(f"• {action}" for action in _family_actions())
    return (
        "💞 Семья и отношения\n\n"
        "Это развлекательные семейные команды, а не игры. Для действий на другого участника ответьте на его сообщение.\n\n"
        f"{lines}"
    )


def _cb(owner_id: int, action: str) -> str:
    return f"funhelp:{owner_id}:{action}"


def _main_markup(owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎭 Все действия", callback_data=_cb(owner_id, "all:0"))],
        [InlineKeyboardButton(text="💞 Семья и отношения", callback_data=_cb(owner_id, "family"))],
        [InlineKeyboardButton(text="✖️ Закрыть", callback_data=_cb(owner_id, "close"))],
    ])


def _back_markup(owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ К развлечениям", callback_data=_cb(owner_id, "home"))],
        [InlineKeyboardButton(text="✖️ Закрыть", callback_data=_cb(owner_id, "close"))],
    ])


def _all_markup(owner_id: int, page: int) -> InlineKeyboardMarkup:
    pages = max(1, math.ceil(len(_all_actions()) / PAGE_SIZE))
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=_cb(owner_id, f"all:{page - 1}")))
    if page + 1 < pages:
        nav.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=_cb(owner_id, f"all:{page + 1}")))
    rows = [nav] if nav else []
    rows.extend(_back_markup(owner_id).inline_keyboard)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _owner_or_reject(callback: CallbackQuery) -> int | None:
    parts = (callback.data or "").split(":", 2)
    if len(parts) != 3 or not parts[1].isdigit():
        await callback.answer("Это меню устарело. Напишите «развлечения» ещё раз.", show_alert=True)
        return None
    owner_id = int(parts[1])
    if callback.from_user.id != owner_id:
        await callback.answer(FOREIGN_BUTTON_NOTICE, show_alert=True)
        return None
    return owner_id


@router.message(F.chat.type.in_(GROUP_TYPES), F.text.casefold().in_(OPEN_WORDS))
async def entertainment_help(message: Message) -> None:
    if message.from_user is not None:
        await message.reply(_main_text(), reply_markup=_main_markup(message.from_user.id))


@router.callback_query(F.data.regexp(r"^funhelp:\d+:home$"))
async def entertainment_home(callback: CallbackQuery) -> None:
    owner_id = await _owner_or_reject(callback)
    if owner_id is not None and callback.message is not None:
        await callback.message.edit_text(_main_text(), reply_markup=_main_markup(owner_id))
        await callback.answer()


@router.callback_query(F.data.regexp(r"^funhelp:\d+:all:\d+$"))
async def entertainment_all(callback: CallbackQuery) -> None:
    owner_id = await _owner_or_reject(callback)
    if owner_id is None or callback.message is None:
        return
    page = int((callback.data or "").rsplit(":", 1)[1])
    pages = max(1, math.ceil(len(_all_actions()) / PAGE_SIZE))
    page = max(0, min(page, pages - 1))
    await callback.message.edit_text(_page_text(page), reply_markup=_all_markup(owner_id, page))
    await callback.answer()


@router.callback_query(F.data.regexp(r"^funhelp:\d+:family$"))
async def entertainment_family(callback: CallbackQuery) -> None:
    owner_id = await _owner_or_reject(callback)
    if owner_id is None or callback.message is None:
        return
    await callback.message.edit_text(_family_text(), reply_markup=_back_markup(owner_id))
    await callback.answer()


@router.callback_query(F.data.regexp(r"^funhelp:\d+:close$"))
async def entertainment_close(callback: CallbackQuery) -> None:
    owner_id = await _owner_or_reject(callback)
    if owner_id is not None and callback.message is not None:
        await callback.message.delete()
        await callback.answer()


@router.callback_query(F.data.regexp(r"^funhelp:(home|relations|family|fight|absurd|crime|random|suggest|close)$"))
async def entertainment_legacy_menu(callback: CallbackQuery) -> None:
    await callback.answer("Это меню устарело. Напишите «развлечения» ещё раз.", show_alert=True)
