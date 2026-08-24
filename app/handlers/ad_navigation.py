from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.services.ui import panel_header


router = Router(name=__name__)


def _ads_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🛒 Купить рекламу", callback_data="ads:buy"),
            InlineKeyboardButton(text="💼 Продать ОП", callback_data="ads:sell"),
        ],
        [
            InlineKeyboardButton(text="📢 Мои рекламные посты", callback_data="gpost:mine"),
            InlineKeyboardButton(text="📨 Мои запросы ОП", callback_data="reqdeal:buyer"),
        ],
        [InlineKeyboardButton(text="📥 Входящие заявки ОП", callback_data="reqdeal:seller")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="panel:home")],
    ])


@router.callback_query(F.data == "ads:home")
async def ads_home(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        panel_header(
            "Реклама",
            "Здесь два разных формата.\n\n"
            "📣 Рекламный пост — покупатель собирает пост, создатель Mimoru проверяет его, после одобрения выставляется счёт, а оплаченный пост автоматически публикуется во всех активных группах Mimoru.\n\n"
            "✅ Обязательная подписка — владельцы групп публикуют свои предложения, покупатель сам выбирает площадку, связывается с продавцом и отправляет ему запрос.",
        ),
        reply_markup=_ads_home_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "ads:buy")
async def ads_buy(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        panel_header(
            "Купить рекламу",
            "Выберите формат. Для ОП вы сами выбираете конкретное объявление владельца группы. Рекламный пост после проверки создателем Mimoru распространяется по всей сети групп.",
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Купить обязательную подписку", callback_data="ads:buy:required")],
            [InlineKeyboardButton(text="📣 Создать рекламный пост", callback_data="ads:buy:post")],
            [InlineKeyboardButton(text="◀️ Реклама", callback_data="ads:home")],
        ]),
    )
    await callback.answer()


@router.callback_query(F.data == "ads:sell")
async def ads_sell(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        panel_header(
            "Продать обязательную подписку",
            "Создайте объявление для одной из своих групп: покупатель увидит только название группы, количество участников, минимальный срок и цену. ID и @username площадки в каталоге не показываются.\n\n"
            "Покупатель может связаться с вами напрямую, а официальный запрос вы принимаете или отклоняете кнопкой.",
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Мои объявления ОП", callback_data="ads:sell:required")],
            [InlineKeyboardButton(text="📥 Входящие заявки", callback_data="reqdeal:seller")],
            [InlineKeyboardButton(text="◀️ Реклама", callback_data="ads:home")],
        ]),
    )
    await callback.answer()
