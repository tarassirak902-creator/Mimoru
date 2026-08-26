from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.promo_redemption import redeem_code_for_group
from app.services.promos import normalize_promo_code


router = Router(name=__name__)


@router.message(
    F.chat.type == "private",
    F.text.regexp(r"(?i)^промокод [A-Za-z0-9_-]+ \d+$"),
)
async def legacy_promo_text(message: Message, session: AsyncSession) -> None:
    """Keep the old promo syntax on the current atomic redemption boundary."""
    if message.from_user is None:
        return
    _, raw_code, raw_group_id = (message.text or "").split()
    code = normalize_promo_code(raw_code)
    if not code:
        await message.answer("Промокод недействителен.")
        return
    await redeem_code_for_group(
        message,
        session,
        user_id=message.from_user.id,
        group_id=int(raw_group_id),
        code=code,
    )


@router.callback_query(F.data.regexp(r"^plan_buy:\d+:(standard|pro)$"))
async def legacy_plan_buy(callback: CallbackQuery) -> None:
    """Keep old Telegram buttons usable after the tariff flow redesign."""
    _, raw_group_id, plan_code = callback.data.split(":")
    await callback.message.edit_text(
        "Выберите актуальный вариант оформления тарифа для этой группы.",
        reply_markup=None,
    )
    await callback.message.edit_reply_markup(
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"💎 Открыть {plan_code.upper()}",
                callback_data=f"plans_apply:{plan_code}:{raw_group_id}:group",
            )],
            [InlineKeyboardButton(text="◀️ К тарифам группы", callback_data=f"plan:{raw_group_id}")],
        ])
    )
    await callback.answer()
