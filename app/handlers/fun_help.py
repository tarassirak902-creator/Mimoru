from __future__ import annotations

import math
import random

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.handlers.fun_commands import ACTIONS
from app.handlers.fun_social import PROPOSALS


router = Router(name=__name__)
GROUP_TYPES = {"group", "supergroup"}
OPEN_WORDS = {"развлечения", "игры"}
FOREIGN_BUTTON_NOTICE = "Не для тебя мать кнопки прислала, отдыхай! Выпей лучше валерьянки и узбогойся..."
PAGE_SIZE = 18

CATEGORIES: dict[str, tuple[str, str]] = {
    "relations": ("❤️ Отношения", "Как использовать: ответьте на сообщение участника одной из фраз ниже. Результат появится сразу.\n\nобнять · поцеловать · подкатить · сделать комплимент · соблазнить · зафрендзонить\n\nЕсли хотите действие, где второй участник должен согласиться, откройте «💌 Все предложения»."),
    "family": ("💍 Семейные шутки", "Как использовать: ответьте на сообщение участника одной из фраз ниже. Результат появится сразу.\n\nпомириться · поссориться · усыновить · удочерить · выгнать из дома\n\nПредложение брака находится отдельно в «💌 Все предложения»."),
    "fight": ("🥊 Шуточные действия", "Как использовать: ответьте на сообщение участника одной из фраз ниже. Результат появится сразу.\n\nударить · пнуть · дать леща · дать подзатыльник · укусить · покусать\n\nДуэль и драка с согласием второго участника находятся отдельно в «💌 Все предложения»."),
    "absurd": ("🪄 Абсурд", "Как использовать: ответьте на сообщение участника одной из фраз ниже. Результат появится сразу.\n\nпонюхать · понюхать волосы · потыкать · завернуть в плед · превратить в жабу · превратить в кота · превратить в дошик · клонировать · призвать · изгнать · дать вайфай · отключить интернет\n\nЭто только шутки — реальные права и ограничения участников не меняются."),
    "crime": ("💰 Криминал и деньги", "Как использовать: ответьте на сообщение участника одной из фраз ниже. Результат появится сразу.\n\nограбить · похитить · суд · арестовать · вызвать полицию · продать · купить · обменять · заскамить · попросить денег · подарить миллион\n\nУ некоторых действий несколько случайных исходов."),
    "random": ("🎲 Случайные события", "Как использовать: ответьте на сообщение участника одной из фраз ниже. Mimoru случайно выберет исход.\n\nподкатить · ограбить · похитить · ударить · суд"),
}

RANDOM_SUGGESTIONS = ["завернуть в плед", "понюхать волосы", "ограбить", "превратить в дошик", "дать дошик", "пнуть под зад", "подкатить", "загуглить", "подарить миллион", "украсть носок", "сдать бабушке", "клонировать"]


def _main_text() -> str:
    return (
        "🎮 Mimoru · Игры и развлечения\n\n"
        "Ответьте на сообщение участника нужным словом или фразой. Обычные действия срабатывают сразу, а в предложениях второй участник должен принять или отклонить предложение.\n\n"
        "🎭 Все действия — полный список шуточных действий.\n"
        "💌 Все предложения — брак, свидание, признание, дуэль и другие предложения.\n\n"
        "Полезно знать:\n"
        "• моя стата игр — ваша статистика в этой группе\n"
        "• топ игр — самые активные игроки группы\n"
        "• /imunitet — запретить или снова разрешить случайные действия самой Mimoru на вас\n"
        "• между обычными действиями одного участника действует пауза 3 секунды\n\n"
        "Выберите, что хотите посмотреть."
    )


def _all_actions() -> list[str]:
    return sorted(ACTIONS, key=str.casefold)


def _proposal_actions() -> list[str]:
    return sorted(PROPOSALS, key=str.casefold)


def _all_page_text(page: int) -> str:
    actions = _all_actions(); pages = max(1, math.ceil(len(actions) / PAGE_SIZE)); page = max(0, min(page, pages - 1)); start = page * PAGE_SIZE
    lines = "\n".join(f"• {action}" for action in actions[start:start + PAGE_SIZE])
    return f"🎭 Все действия\n\nКак использовать:\n1. Найдите сообщение участника.\n2. Ответьте на него одним из слов или фраз ниже.\n3. Mimoru сразу покажет шуточный результат.\n\n{lines}\n\nСтраница {page + 1} из {pages} · Всего действий: {len(actions)}"


def _proposals_text() -> str:
    lines = "\n".join(f"• {action}" for action in _proposal_actions())
    return f"💌 Все предложения\n\nКак использовать:\n1. Найдите сообщение участника.\n2. Ответьте на него одной из фраз ниже.\n3. Mimoru отправит предложение с кнопками «Принять» и «Отказать».\n4. Ответить сможет только адресат.\n\n{lines}\n\nПосле принятого брака:\n• брак или мой брак — посмотреть партнёра\n• развестись — завершить брак"


def _cb(owner_id: int, action: str) -> str:
    return f"funhelp:{owner_id}:{action}"


def _main_markup(owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎭 Все действия", callback_data=_cb(owner_id, "all:0"))],
        [InlineKeyboardButton(text="💌 Все предложения", callback_data=_cb(owner_id, "proposals"))],
        [InlineKeyboardButton(text="❤️ Отношения", callback_data=_cb(owner_id, "relations")), InlineKeyboardButton(text="💍 Семья", callback_data=_cb(owner_id, "family"))],
        [InlineKeyboardButton(text="🥊 Действия", callback_data=_cb(owner_id, "fight")), InlineKeyboardButton(text="🪄 Абсурд", callback_data=_cb(owner_id, "absurd"))],
        [InlineKeyboardButton(text="💰 Криминал", callback_data=_cb(owner_id, "crime")), InlineKeyboardButton(text="🎲 Рандом", callback_data=_cb(owner_id, "random"))],
        [InlineKeyboardButton(text="🎯 Что попробовать?", callback_data=_cb(owner_id, "suggest"))],
        [InlineKeyboardButton(text="✖️ Закрыть", callback_data=_cb(owner_id, "close"))],
    ])


def _back_markup(owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎭 Все действия", callback_data=_cb(owner_id, "all:0"))], [InlineKeyboardButton(text="💌 Все предложения", callback_data=_cb(owner_id, "proposals"))], [InlineKeyboardButton(text="◀️ К играм", callback_data=_cb(owner_id, "home"))], [InlineKeyboardButton(text="✖️ Закрыть", callback_data=_cb(owner_id, "close"))]])


def _all_markup(owner_id: int, page: int) -> InlineKeyboardMarkup:
    actions = _all_actions(); pages = max(1, math.ceil(len(actions) / PAGE_SIZE)); page = max(0, min(page, pages - 1)); nav = []
    if page > 0: nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=_cb(owner_id, f"all:{page - 1}")))
    if page + 1 < pages: nav.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=_cb(owner_id, f"all:{page + 1}")))
    rows = [nav] if nav else []
    rows.extend([[InlineKeyboardButton(text="💌 Все предложения", callback_data=_cb(owner_id, "proposals"))], [InlineKeyboardButton(text="◀️ К играм", callback_data=_cb(owner_id, "home"))], [InlineKeyboardButton(text="✖️ Закрыть", callback_data=_cb(owner_id, "close"))]])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _owner_or_reject(callback: CallbackQuery) -> int | None:
    parts = (callback.data or "").split(":", 2)
    if len(parts) != 3 or not parts[1].isdigit():
        await callback.answer("Это меню устарело. Вызовите /games ещё раз.", show_alert=True); return None
    owner_id = int(parts[1])
    if callback.from_user.id != owner_id:
        await callback.answer(FOREIGN_BUTTON_NOTICE, show_alert=True); return None
    return owner_id


@router.message(F.chat.type.in_(GROUP_TYPES), F.text.casefold().in_(OPEN_WORDS))
async def entertainment_help(message: Message) -> None:
    if message.from_user is not None: await message.reply(_main_text(), reply_markup=_main_markup(message.from_user.id))


@router.callback_query(F.data.regexp(r"^funhelp:\d+:home$"))
async def entertainment_home(callback: CallbackQuery) -> None:
    owner_id = await _owner_or_reject(callback)
    if owner_id is not None and callback.message is not None: await callback.message.edit_text(_main_text(), reply_markup=_main_markup(owner_id)); await callback.answer()


@router.callback_query(F.data.regexp(r"^funhelp:\d+:all:\d+$"))
async def entertainment_all(callback: CallbackQuery) -> None:
    owner_id = await _owner_or_reject(callback)
    if owner_id is None or callback.message is None: return
    page = min(int((callback.data or "").rsplit(":", 1)[1]), max(1, math.ceil(len(_all_actions()) / PAGE_SIZE)) - 1)
    await callback.message.edit_text(_all_page_text(page), reply_markup=_all_markup(owner_id, page)); await callback.answer()


@router.callback_query(F.data.regexp(r"^funhelp:\d+:proposals$"))
async def entertainment_proposals(callback: CallbackQuery) -> None:
    owner_id = await _owner_or_reject(callback)
    if owner_id is None or callback.message is None: return
    await callback.message.edit_text(_proposals_text(), reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎭 Все действия", callback_data=_cb(owner_id, "all:0"))], [InlineKeyboardButton(text="◀️ К играм", callback_data=_cb(owner_id, "home"))], [InlineKeyboardButton(text="✖️ Закрыть", callback_data=_cb(owner_id, "close"))]])); await callback.answer()


@router.callback_query(F.data.regexp(r"^funhelp:\d+:(relations|family|fight|absurd|crime|random)$"))
async def entertainment_category(callback: CallbackQuery) -> None:
    owner_id = await _owner_or_reject(callback)
    if owner_id is None or callback.message is None: return
    key = (callback.data or "").rsplit(":", 1)[1]; title, body = CATEGORIES[key]
    await callback.message.edit_text(f"{title}\n\n{body}", reply_markup=_back_markup(owner_id)); await callback.answer()


@router.callback_query(F.data.regexp(r"^funhelp:\d+:suggest$"))
async def entertainment_suggestion(callback: CallbackQuery) -> None:
    owner_id = await _owner_or_reject(callback)
    if owner_id is None or callback.message is None: return
    action = random.choice(RANDOM_SUGGESTIONS)
    await callback.message.edit_text(f"🎯 Что попробовать?\n\nОтветьте на сообщение участника этой фразой:\n\n{action}\n\nMimoru сразу покажет результат.", reply_markup=_back_markup(owner_id)); await callback.answer()


@router.callback_query(F.data.regexp(r"^funhelp:\d+:close$"))
async def entertainment_close(callback: CallbackQuery) -> None:
    owner_id = await _owner_or_reject(callback)
    if owner_id is not None and callback.message is not None: await callback.message.delete(); await callback.answer()


@router.callback_query(F.data.regexp(r"^funhelp:(home|relations|family|fight|absurd|crime|random|suggest|close)$"))
async def entertainment_legacy_menu(callback: CallbackQuery) -> None:
    await callback.answer("Это меню устарело. Вызовите /games ещё раз.", show_alert=True)
