from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group, PromoCode
from app.services.promo_redemption import PromoRedemptionError, redeem_promo_code, redeem_promo_id
from app.services.promos import normalize_promo_code


router = Router(name=__name__)


def _group_choice_markup(groups: list[Group], promo_id: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=group.title[:58],
            callback_data=f"promo_redeem:{group.id}:{promo_id}",
        )]
        for group in groups[:50]
    ]
    rows.append([InlineKeyboardButton(text="✖️ Отмена", callback_data="panel:plans")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _send_redemption_result(message: Message, result) -> None:
    await message.answer(
        "✅ Промокод применён.\n\n"
        f"Тариф: {result.plan_code.upper()}\n"
        f"Бонус: {result.bonus_days} дней\n"
        f"Действует до: {result.expires_at:%d.%m.%Y %H:%M UTC}"
    )


async def _redeem_code_for_group(
    message: Message,
    session: AsyncSession,
    *,
    user_id: int,
    group_id: int,
    code: str,
) -> bool:
    try:
        result = await redeem_promo_code(
            session,
            user_telegram_id=user_id,
            group_id=group_id,
            raw_code=code,
        )
        await session.commit()
    except PromoRedemptionError as exc:
        await message.answer(str(exc))
        return False
    await _send_redemption_result(message, result)
    return True


async def _redeem_id_for_group(
    message: Message,
    session: AsyncSession,
    *,
    user_id: int,
    group_id: int,
    promo_id: int,
) -> bool:
    try:
        result = await redeem_promo_id(
            session,
            user_telegram_id=user_id,
            group_id=group_id,
            promo_id=promo_id,
        )
        await session.commit()
    except PromoRedemptionError as exc:
        await message.answer(str(exc))
        return False
    await _send_redemption_result(message, result)
    return True


@router.message(Command("promo"), F.chat.type == "private")
async def promo_command(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not normalize_promo_code(parts[1]):
        await message.answer(
            "🎟 Промокод\n\n"
            "Отправьте код после команды:\n"
            "/promo START-7\n\n"
            "Промокод применяется только к вашей активной группе."
        )
        return
    code = normalize_promo_code(parts[1])
    promo_id = await session.scalar(select(PromoCode.id).where(PromoCode.code == code).limit(1))
    if promo_id is None:
        await message.answer("Промокод не найден.")
        return
    groups = list((await session.scalars(
        select(Group).where(
            Group.owner_telegram_id == message.from_user.id,
            Group.is_active.is_(True),
        ).order_by(Group.created_at.desc())
    )).all())
    if not groups:
        await message.answer("У вас нет активных групп, к которым можно применить промокод.")
        return
    if len(groups) == 1:
        await _redeem_code_for_group(
            message,
            session,
            user_id=message.from_user.id,
            group_id=groups[0].id,
            code=code,
        )
        return
    await message.answer(
        "Выберите свою группу, к которой применить промокод:",
        reply_markup=_group_choice_markup(groups, int(promo_id)),
    )


@router.message(
    F.chat.type == "private",
    F.text.regexp(r"(?i)^промокод [A-Za-z0-9_-]+ \d+$"),
)
async def legacy_promo_text(message: Message, session: AsyncSession) -> None:
    """Keep the old promo syntax, but use the same atomic redemption boundary."""
    if message.from_user is None:
        return
    _, raw_code, raw_group_id = (message.text or "").split()
    code = normalize_promo_code(raw_code)
    if not code:
        await message.answer("Промокод недействителен.")
        return
    await _redeem_code_for_group(
        message,
        session,
        user_id=message.from_user.id,
        group_id=int(raw_group_id),
        code=code,
    )


@router.callback_query(F.data.regexp(r"^promo_redeem:\d+:\d+$"))
async def promo_choose_group(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.message is None or callback.message.chat.type != "private":
        await callback.answer("Введите /promo CODE в личном чате с Mimoru.", show_alert=True)
        return
    _, raw_group_id, raw_promo_id = callback.data.split(":")
    ok = await _redeem_id_for_group(
        callback.message,
        session,
        user_id=callback.from_user.id,
        group_id=int(raw_group_id),
        promo_id=int(raw_promo_id),
    )
    await callback.answer("Промокод применён" if ok else "Промокод не применён")


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
