from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group, GroupSubscriptionEvent, PromoCode
from app.services.access import is_service_owner
from app.services.client_access import set_client_blocked
from app.services.plans import effective_plan
from app.services.promos import normalize_promo_code
from app.services.ui import clean_ui_text, panel_header


router = Router(name=__name__)


def _plan_keyboard(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧪 TRIAL · 7 дней", callback_data=f"service_plan_confirm:{group_id}:trial:7")],
        [InlineKeyboardButton(text="⭐ STANDARD · 30 дней", callback_data=f"service_plan_confirm:{group_id}:standard:30")],
        [InlineKeyboardButton(text="💎 PRO · 30 дней", callback_data=f"service_plan_confirm:{group_id}:pro:30")],
        [InlineKeyboardButton(text="🆓 Перевести на FREE", callback_data=f"service_plan_confirm:{group_id}:free:0")],
        [InlineKeyboardButton(text="◀️ К карточке группы", callback_data=f"service_group:{group_id}")],
    ])


def _promo_help() -> str:
    return (
        "🎟 Управление промокодами\n\n"
        "/promos — список кодов\n"
        "/promo_create CODE PLAN DAYS MAX_USES [YYYY-MM-DD]\n"
        "/promo_off CODE — отключить код\n\n"
        "PLAN: trial, standard или pro. Дата окончания необязательна и задаётся в UTC."
    )


async def _locked_group(session: AsyncSession, group_id: int) -> Group | None:
    return await session.scalar(
        select(Group).where(Group.id == group_id).with_for_update()
    )


async def _apply_manual_plan(
    session: AsyncSession,
    *,
    group_id: int,
    actor_id: int,
    plan_code: str,
    days: int,
) -> Group | None:
    """Serialize all manual plan changes with payment/promo group mutations."""
    group = await _locked_group(session, group_id)
    if group is None:
        return None
    now = datetime.now(timezone.utc)
    if plan_code == "free":
        group.plan_code = "free"
        group.plan_expires_at = None
    else:
        current_code = effective_plan(group)
        start = (
            group.plan_expires_at
            if current_code == plan_code and group.plan_expires_at and group.plan_expires_at > now
            else now
        )
        group.plan_code = plan_code
        group.plan_expires_at = start + timedelta(days=days)
    session.add(GroupSubscriptionEvent(
        group_id=group.id,
        actor_telegram_id=actor_id,
        event_type="admin_grant",
        plan_code=plan_code,
        expires_at=group.plan_expires_at,
    ))
    await session.commit()
    return group


async def _render_plan_result(callback: CallbackQuery, group: Group) -> None:
    expires = group.plan_expires_at.strftime("%d.%m.%Y %H:%M UTC") if group.plan_expires_at else "без срока"
    await callback.message.edit_text(
        panel_header(
            "Управление тарифом",
            f"{group.title}\n\nТариф изменён.\nТекущий тариф: {effective_plan(group).upper()}\nСрок: {expires}",
        ),
        reply_markup=_plan_keyboard(group.id),
    )
    await callback.answer("Тариф обновлён")


@router.message(Command("promos"), F.chat.type == "private")
async def service_promos(message: Message, session: AsyncSession) -> None:
    if message.from_user is None or not is_service_owner(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    rows = list((await session.scalars(
        select(PromoCode).order_by(PromoCode.created_at.desc()).limit(50)
    )).all())
    lines = [_promo_help()]
    if rows:
        lines += ["", "Последние промокоды:"]
        for promo in rows:
            expires = promo.expires_at.strftime("%d.%m.%Y") if promo.expires_at else "без срока"
            status = "✅" if promo.active else "⛔"
            lines.append(
                f"{status} {promo.code} · {promo.plan_code.upper()} +{promo.bonus_days}д · "
                f"{promo.current_uses}/{promo.max_uses} · до {expires}"
            )
    await message.answer("\n".join(lines))


@router.message(Command("promo_create"), F.chat.type == "private")
async def service_promo_create(message: Message, session: AsyncSession) -> None:
    if message.from_user is None or not is_service_owner(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    parts = (message.text or "").split()
    if len(parts) not in {5, 6}:
        await message.answer(_promo_help())
        return
    code = normalize_promo_code(parts[1])
    plan_code = parts[2].casefold()
    try:
        bonus_days = int(parts[3])
        max_uses = int(parts[4])
    except ValueError:
        await message.answer("DAYS и MAX_USES должны быть целыми числами.")
        return
    if not code or len(code) > 64:
        await message.answer("Код должен содержать от 1 до 64 символов.")
        return
    if plan_code not in {"trial", "standard", "pro"}:
        await message.answer("PLAN должен быть trial, standard или pro.")
        return
    if not 1 <= bonus_days <= 3650 or not 1 <= max_uses <= 100000:
        await message.answer("DAYS: 1–3650, MAX_USES: 1–100000.")
        return

    expires_at = None
    if len(parts) == 6:
        try:
            expiry_day = datetime.strptime(parts[5], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            await message.answer("Дата должна быть в формате YYYY-MM-DD.")
            return
        expires_at = expiry_day + timedelta(days=1)
        if expires_at <= datetime.now(timezone.utc):
            await message.answer("Дата окончания должна быть в будущем.")
            return

    session.add(PromoCode(
        code=code,
        plan_code=plan_code,
        bonus_days=bonus_days,
        max_uses=max_uses,
        current_uses=0,
        active=True,
        expires_at=expires_at,
        created_by_telegram_id=message.from_user.id,
    ))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        await message.answer("Промокод с таким кодом уже существует.")
        return
    await message.answer(
        f"✅ Промокод {code} создан: {plan_code.upper()} +{bonus_days} дней, "
        f"лимит {max_uses}."
    )


async def _disable_promo_locked(
    session: AsyncSession,
    raw_code: str,
) -> PromoCode | None:
    code = normalize_promo_code(raw_code)
    promo = await session.scalar(
        select(PromoCode).where(PromoCode.code == code).with_for_update()
    )
    if promo is None:
        return None
    promo.active = False
    await session.commit()
    return promo


@router.message(Command("promo_off"), F.chat.type == "private")
async def service_promo_off(message: Message, session: AsyncSession) -> None:
    if message.from_user is None or not is_service_owner(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /promo_off CODE")
        return
    promo = await _disable_promo_locked(session, parts[1])
    if promo is None:
        await message.answer("Промокод не найден.")
        return
    await message.answer(f"⛔ Промокод {promo.code} отключён.")


@router.message(F.chat.type == "private", F.text.regexp(r"(?i)^отключить промокод [A-Za-z0-9_-]+$"))
async def legacy_promo_off_serialized(message: Message, session: AsyncSession) -> None:
    if message.from_user is None or not is_service_owner(message.from_user.id):
        return
    promo = await _disable_promo_locked(session, (message.text or "").split()[-1])
    if promo is None:
        await message.answer("Промокод не найден.")
        return
    await message.answer(f"✅ Промокод {promo.code} отключён.")


@router.callback_query(F.data.regexp(r"^service_client_action:\d+:(block|unblock)$"))
async def client_action_serialized(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_service_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    _, raw_tid, action = callback.data.split(":")
    result = await set_client_blocked(
        session,
        telegram_id=int(raw_tid),
        blocked=action == "block",
    )
    if result is None:
        await callback.answer("Клиент не найден.", show_alert=True)
        return
    callback.data = f"service_client:{raw_tid}"
    from app.handlers.service_management import client_card

    await client_card(callback, session)


@router.message(F.chat.type == "private", F.text.regexp(r"(?i)^заблокировать клиента \d+$"))
async def legacy_block_client_serialized(message: Message, session: AsyncSession) -> None:
    if message.from_user is None or not is_service_owner(message.from_user.id):
        return
    telegram_id = int((message.text or "").split()[-1])
    result = await set_client_blocked(session, telegram_id=telegram_id, blocked=True)
    if result is None:
        await message.answer("Клиент не найден.")
        return
    await message.answer(
        f"✅ Клиент {telegram_id} заблокирован. Отключено групп: {result.disabled_groups}."
    )


@router.message(F.chat.type == "private", F.text.regexp(r"(?i)^разблокировать клиента \d+$"))
async def legacy_unblock_client_serialized(message: Message, session: AsyncSession) -> None:
    if message.from_user is None or not is_service_owner(message.from_user.id):
        return
    telegram_id = int((message.text or "").split()[-1])
    result = await set_client_blocked(session, telegram_id=telegram_id, blocked=False)
    if result is None:
        await message.answer("Клиент не найден.")
        return
    await message.answer(f"✅ Клиент {telegram_id} разблокирован. Группы включаются отдельно.")


@router.message(F.chat.type == "private", F.text.regexp(r"(?i)^выдать тариф \d+ (free|standard|pro|trial) \d+д$"))
async def grant_plan_serialized(message: Message, session: AsyncSession) -> None:
    if message.from_user is None or not is_service_owner(message.from_user.id):
        return
    _, _, raw_group_id, plan_code, raw_days = (message.text or "").casefold().split()
    days = int(raw_days[:-1])
    if days < 0 or days > 3650:
        await message.answer("Срок тарифа должен быть от 0 до 3650 дней.")
        return
    group = await _apply_manual_plan(
        session,
        group_id=int(raw_group_id),
        actor_id=message.from_user.id,
        plan_code=plan_code,
        days=days,
    )
    if group is None:
        await message.answer("Группа не найдена.")
        return
    expires = group.plan_expires_at.strftime("%d.%m.%Y") if group.plan_expires_at else "без срока"
    await message.answer(
        f"✅ Тариф {plan_code} выдан группе «{clean_ui_text(group.title)}» до {expires}."
    )


@router.message(F.chat.type == "private", F.text.regexp(r"(?i)^тестовый период \d+ \d+д$"))
async def grant_trial_serialized(message: Message, session: AsyncSession) -> None:
    if message.from_user is None or not is_service_owner(message.from_user.id):
        return
    _, _, raw_group_id, raw_days = (message.text or "").casefold().split()
    days = int(raw_days[:-1])
    if not 1 <= days <= 3650:
        await message.answer("Срок TRIAL должен быть от 1 до 3650 дней.")
        return
    group = await _apply_manual_plan(
        session,
        group_id=int(raw_group_id),
        actor_id=message.from_user.id,
        plan_code="trial",
        days=days,
    )
    if group is None:
        await message.answer("Группа не найдена.")
        return
    await message.answer(
        f"✅ Тестовый период продлён до {group.plan_expires_at:%d.%m.%Y}."
    )


@router.callback_query(F.data.regexp(r"^service_plan_grant:\d+:(free|trial|standard|pro):(0|7|30)$"))
async def service_plan_grant_serialized(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_service_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    _, raw_gid, plan_code, raw_days = callback.data.split(":")
    days = int(raw_days)
    if (plan_code, days) not in {("trial", 7), ("standard", 30), ("pro", 30), ("free", 0)}:
        await callback.answer("Некорректный тариф.", show_alert=True)
        return
    group = await _apply_manual_plan(
        session,
        group_id=int(raw_gid),
        actor_id=callback.from_user.id,
        plan_code=plan_code,
        days=days,
    )
    if group is None:
        await callback.answer("Группа не найдена.", show_alert=True)
        return
    await _render_plan_result(callback, group)


@router.callback_query(F.data.regexp(r"^service_plan_apply:\d+:(trial|standard|pro|free):(0|7|30)$"))
async def service_plan_apply_serialized(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_service_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    _, raw_gid, plan_code, raw_days = callback.data.split(":")
    days = int(raw_days)
    if (plan_code, days) not in {("trial", 7), ("standard", 30), ("pro", 30), ("free", 0)}:
        await callback.answer("Некорректный тариф.", show_alert=True)
        return
    group = await _apply_manual_plan(
        session,
        group_id=int(raw_gid),
        actor_id=callback.from_user.id,
        plan_code=plan_code,
        days=days,
    )
    if group is None:
        await callback.answer("Группа не найдена.", show_alert=True)
        return
    await _render_plan_result(callback, group)


@router.callback_query(F.data.regexp(r"^service_plan_action:\d+:(free|trial|standard|pro):(0|7|30)$"))
async def service_plan_action_fixed(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_service_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    _, raw_gid, plan_code, raw_days = callback.data.split(":")
    days = int(raw_days)
    group = await _apply_manual_plan(
        session,
        group_id=int(raw_gid),
        actor_id=callback.from_user.id,
        plan_code=plan_code,
        days=days,
    )
    if group is None:
        await callback.answer("Группа не найдена.", show_alert=True)
        return
    await _render_plan_result(callback, group)
