from datetime import datetime, timedelta, timezone

import structlog

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Group, Payment, SupportTicket, User
from app.services.plans import effective_plan, remaining_days, subscription_state
from app.services.ui import clean_ui_text, panel_header

router = Router(name=__name__)
settings = get_settings()


def owner(user_id: int) -> bool:
    return user_id in settings.service_owner_ids


def _service_plan_keyboard(group: Group) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧪 Выдать TRIAL · 7 дней", callback_data=f"service_plan_confirm:{group.id}:trial:7")],
        [InlineKeyboardButton(text="⭐ STANDARD · 30 дней", callback_data=f"service_plan_confirm:{group.id}:standard:30")],
        [InlineKeyboardButton(text="💎 PRO · 30 дней", callback_data=f"service_plan_confirm:{group.id}:pro:30")],
        [InlineKeyboardButton(text="🆓 Перевести на FREE", callback_data=f"service_plan_confirm:{group.id}:free:0")],
        [InlineKeyboardButton(text="◀️ К карточке группы", callback_data=f"service_group:{group.id}")],
    ])


def _service_plan_text(group: Group) -> str:
    state = subscription_state(group)
    labels = {
        "free": "FREE",
        "trial": "TRIAL",
        "active": effective_plan(group).upper(),
        "expired": f"{(group.plan_code or 'free').upper()} · истёк",
    }
    expires = group.plan_expires_at.strftime("%d.%m.%Y %H:%M UTC") if group.plan_expires_at else "без срока"
    days = remaining_days(group)
    text = panel_header("Управление тарифом", group.title)
    text += f"\n\nТекущий тариф: {labels[state]}\nСрок: {expires}"
    if days is not None:
        text += f"\nОсталось дней: {days}"
    text += "\n\nВыберите действие. Повторная выдача того же активного тарифа продлевает его срок. При смене тарифа новый срок начинается с текущего момента."
    return text


@router.callback_query(F.data.regexp(r"^service_plan:\d+$"))
async def service_plan(callback: CallbackQuery, session: AsyncSession) -> None:
    if not owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    group = await session.get(Group, int(callback.data.split(":")[1]))
    if group is None:
        await callback.answer("Группа не найдена.", show_alert=True)
        return
    await callback.message.edit_text(_service_plan_text(group), reply_markup=_service_plan_keyboard(group))
    await callback.answer()


@router.callback_query(F.data.regexp(r"^service_plan_confirm:\d+:(trial|standard|pro|free):(0|7|30)$"))
async def service_plan_confirm(callback: CallbackQuery, session: AsyncSession) -> None:
    if not owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    _, raw_group_id, plan_code, raw_days = callback.data.split(":")
    group = await session.get(Group, int(raw_group_id))
    if group is None:
        await callback.answer("Группа не найдена.", show_alert=True)
        return
    days = int(raw_days)
    if (plan_code, days) not in {("trial", 7), ("standard", 30), ("pro", 30), ("free", 0)}:
        await callback.answer("Некорректный тариф.", show_alert=True)
        return
    action = "перевести группу на FREE" if plan_code == "free" else f"выдать {plan_code.upper()} на {days} дней"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, подтвердить", callback_data=f"service_plan_apply:{group.id}:{plan_code}:{days}")],
        [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"service_plan:{group.id}")],
    ])
    await callback.message.edit_text(
        panel_header("Подтверждение тарифа", f"Группа: {group.title}\n\nБудет выполнено действие: {action}."),
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^service_plan_apply:\d+:(trial|standard|pro|free):(0|7|30)$"))
async def service_plan_apply(callback: CallbackQuery, session: AsyncSession) -> None:
    if not owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    _, raw_group_id, plan_code, raw_days = callback.data.split(":")
    group = await session.get(Group, int(raw_group_id))
    if group is None:
        await callback.answer("Группа не найдена.", show_alert=True)
        return
    days = int(raw_days)
    if (plan_code, days) not in {("trial", 7), ("standard", 30), ("pro", 30), ("free", 0)}:
        await callback.answer("Некорректный тариф.", show_alert=True)
        return

    now = datetime.now(timezone.utc)
    if plan_code == "free":
        group.plan_code = "free"
        group.plan_expires_at = None
    else:
        same_active_plan = group.plan_code == plan_code and group.plan_expires_at and group.plan_expires_at > now
        start = group.plan_expires_at if same_active_plan else now
        group.plan_code = plan_code
        group.plan_expires_at = start + timedelta(days=days)
    await session.commit()

    await callback.message.edit_text(_service_plan_text(group), reply_markup=_service_plan_keyboard(group))
    await callback.answer("Тариф обновлён")


@router.message(F.chat.type == "private", F.text.casefold() == "статистика сервиса")
async def service_stats(message: Message, session: AsyncSession) -> None:
    if not owner(message.from_user.id):
        return
    users = await session.scalar(select(func.count()).select_from(User))
    groups = await session.scalar(select(func.count()).select_from(Group).where(Group.is_active.is_(True)))
    paid = await session.scalar(select(func.count()).select_from(Payment).where(Payment.status == "paid"))
    await message.answer(
        f"Пользователей: {users or 0}\n"
        f"Активных групп: {groups or 0}\n"
        f"Успешных платежей: {paid or 0}"
    )


@router.message(F.chat.type == "private", F.text.regexp(r"(?is)^поддержка .+"))
async def support(message: Message, session: AsyncSession) -> None:
    text = clean_ui_text(message.text.split(maxsplit=1)[1][:4000])
    ticket = SupportTicket(user_telegram_id=message.from_user.id, text=text)
    session.add(ticket)
    await session.commit()
    await message.answer(f"✅ Обращение #{ticket.id} создано. Мы увидим его в панели поддержки.")
    recipients = set(settings.service_owner_ids)
    if settings.support_chat_id:
        recipients.add(settings.support_chat_id)
    for recipient in recipients:
        try:
            await message.bot.send_message(
                recipient,
                f"🆘 Новое обращение #{ticket.id}\n"
                f"Пользователь: {message.from_user.id}\n\n{text}",
            )
        except Exception as error:
            structlog.get_logger().warning(
                "support_notification_failed",
                ticket_id=ticket.id,
                recipient=recipient,
                error=str(error),
            )


@router.message(F.chat.type == "private", F.text.casefold() == "обращения")
async def tickets(message: Message, session: AsyncSession) -> None:
    if not owner(message.from_user.id):
        return
    rows = (await session.scalars(
        select(SupportTicket).where(SupportTicket.status == "new").order_by(SupportTicket.created_at.desc()).limit(30)
    )).all()
    await message.answer(
        "Новые обращения\n" + (
            "\n".join(f"#{x.id} {x.user_telegram_id}: {clean_ui_text(x.text[:120])}" for x in rows)
            if rows else "Нет новых обращений."
        )
    )


@router.message(F.chat.type == "private", F.text.regexp(r"(?i)^закрыть обращение \d+$"))
async def close_ticket(message: Message, session: AsyncSession) -> None:
    if not owner(message.from_user.id):
        return
    ticket_id = int(message.text.split()[-1])
    ticket = await session.get(SupportTicket, ticket_id)
    if ticket is None:
        await message.answer("Обращение не найдено.")
        return
    ticket.status = "closed"
    await session.commit()
    await message.answer(f"✅ Обращение #{ticket_id} закрыто.")


@router.message(F.chat.type == "private", F.text.regexp(r"(?i)^выдать тариф \d+ (free|standard|pro|trial) \d+д$"))
async def grant_plan(message: Message, session: AsyncSession) -> None:
    if not owner(message.from_user.id):
        return
    _, _, raw_group_id, plan_code, raw_days = message.text.casefold().split()
    group = await session.get(Group, int(raw_group_id))
    if group is None:
        await message.answer("Группа не найдена.")
        return
    days = int(raw_days[:-1])
    now = datetime.now(timezone.utc)
    start = group.plan_expires_at if group.plan_expires_at and group.plan_expires_at > now else now
    group.plan_code = plan_code
    group.plan_expires_at = start + timedelta(days=days)
    await session.commit()
    await message.answer(
        f"✅ Тариф {plan_code} выдан группе «{clean_ui_text(group.title)}» до {group.plan_expires_at:%d.%m.%Y}."
    )


@router.message(F.chat.type == "private", F.text.regexp(r"(?i)^отключить группу \d+$"))
async def disable_group(message: Message, session: AsyncSession) -> None:
    if not owner(message.from_user.id):
        return
    group = await session.get(Group, int(message.text.split()[-1]))
    if group is None:
        await message.answer("Группа не найдена.")
        return
    group.is_active = False
    await session.commit()
    await message.answer("✅ Группа отключена от сервиса.")


@router.message(F.chat.type == "private", F.text.regexp(r"(?is)^рассылка(?: .+)?$"))
async def broadcast_shortcut(message: Message) -> None:
    """Keep the old command as a safe shortcut; never bypass preview/confirm."""
    if not owner(message.from_user.id):
        return
    await message.answer(
        "📣 Рассылка теперь создаётся через конструктор. Там можно отдельно настроить текст, изображение и кнопку, проверить предпросмотр и только затем подтвердить отправку по группам.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📣 Открыть конструктор рассылки", callback_data="service:broadcast")],
            [InlineKeyboardButton(text="◀️ Панель Mimoru", callback_data="service:home")],
        ]),
    )
