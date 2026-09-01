from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.fun_models import GameEvent, GroupMarriage
from app.db.models import Complaint, DailyStat, Group, GroupMember, Punishment, User, Warning
from app.db.rank_models import RankAssignment
from app.games.stat_views import render_member_game_stats
from app.services.public_identity import public_user_token
from app.services.ranks import RANK_LABELS
from app.services.repositories import upsert_user


router = Router(name=__name__)
GROUP_TYPES = {"group", "supergroup"}
PROFILE_CALLBACK_PREFIX = "member_profile_v2"
RP_EVENT_TYPES = ("action", "entertainment_action", "relationship_action")

SELF_PROFILE_ALIASES = {
    "моё досье", "мое досье", "личное дело", "моя статистика", "мой профиль", "моя история",
    "мои данные", "что за мной", "проверить себя", "что обо мне", "мой архив",
    "кто я", "моя стата", "моя инфа", "инфа обо мне", "информация обо мне",
}
LOOKUP_ALIASES = {
    "пробить гражданина", "открыть досье", "личное дело", "проверить участника",
    "проверить гражданина", "поднять дело", "карточка участника", "что за ним", "история участника",
    "кто ты", "ты кто", "инфа", "информация",
}


def _profile_keyboard(group_id: int, target_id: int, requester_id: int, active: str) -> InlineKeyboardMarkup:
    def button(view: str, label: str) -> InlineKeyboardButton:
        prefix = "• " if view == active else ""
        return InlineKeyboardButton(
            text=f"{prefix}{label}",
            callback_data=f"{PROFILE_CALLBACK_PREFIX}:{group_id}:{target_id}:{requester_id}:{view}",
        )

    rp_label = "🎭 Мои РП" if target_id == requester_id else "🎭 РП"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [button("profile", "👤 Профиль"), button("history", "⚖️ История")],
            [button("games", "🎮 Игры"), button("rp", rp_label)],
            [button("close", "❌ Закрыть")],
        ]
    )


async def _active_group(session: AsyncSession, chat_id: int) -> Group | None:
    return await session.scalar(
        select(Group).where(Group.telegram_chat_id == chat_id, Group.is_active.is_(True))
    )


async def _user(session: AsyncSession, user_id: int) -> User | None:
    return await session.scalar(select(User).where(User.telegram_id == user_id))


async def _user_name(session: AsyncSession, user_id: int) -> str:
    # Keep identity resolution out of the handler. PlainTextBot replaces this internal
    # token with the current Telegram name/@username and a clickable text_link.
    return public_user_token(user_id)


async def _user_label(session: AsyncSession, user_id: int) -> str:
    return public_user_token(user_id)


def _plural_messages(value: int) -> str:
    n = abs(value) % 100
    n1 = n % 10
    if 10 < n < 20:
        word = "сообщений"
    elif n1 == 1:
        word = "сообщение"
    elif 2 <= n1 <= 4:
        word = "сообщения"
    else:
        word = "сообщений"
    return f"{value} {word}"


def _ago_text(value: datetime | None) -> str:
    if value is None:
        return "неизвестно"
    now = datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    delta = now - value.astimezone(timezone.utc)
    seconds = max(0, int(delta.total_seconds()))
    if seconds < 90:
        return "только что"
    if seconds < 3600:
        return f"{max(1, seconds // 60)} мин назад"
    if seconds < 86400:
        return f"{max(1, seconds // 3600)} ч назад"
    days = seconds // 86400
    if days == 1:
        return "вчера"
    if days <= 7:
        return "на этой неделе"
    if days <= 31:
        return "в этом месяце"
    return value.astimezone(timezone.utc).strftime("%d.%m.%Y")


def _membership_age(value: datetime | None) -> str:
    if value is None:
        return "неизвестно"
    now = datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    days = max(0, (now.date() - value.astimezone(timezone.utc).date()).days)
    years, remaining = divmod(days, 365)
    parts: list[str] = []
    if years:
        ending = (
            "год"
            if years % 10 == 1 and years % 100 != 11
            else "года"
            if years % 10 in {2, 3, 4} and years % 100 not in {12, 13, 14}
            else "лет"
        )
        parts.append(f"{years} {ending}")
    if remaining or not parts:
        parts.append(f"{remaining} дн")
    return " ".join(parts)


async def _marriage_line(session: AsyncSession, group_id: int, user_id: int) -> str:
    marriage = await session.scalar(
        select(GroupMarriage).where(
            GroupMarriage.group_id == group_id,
            GroupMarriage.active.is_(True),
            or_(GroupMarriage.user1_telegram_id == user_id, GroupMarriage.user2_telegram_id == user_id),
        ).order_by(GroupMarriage.created_at.desc())
    )
    if marriage is None:
        return "💍 Брак: не состоит"
    partner_id = (
        marriage.user2_telegram_id
        if marriage.user1_telegram_id == user_id
        else marriage.user1_telegram_id
    )
    partner = await _user_label(session, partner_id)
    since = marriage.created_at.astimezone(timezone.utc).strftime("%d.%m.%Y")
    return f"💍 Брак: в браке с {partner} с {since}"


async def _message_periods(
    session: AsyncSession, group_id: int, user_id: int
) -> tuple[int, int, int, int, int]:
    today = datetime.now(timezone.utc).date()
    today_s = today.isoformat()
    week = (today - timedelta(days=6)).isoformat()
    month = (today - timedelta(days=29)).isoformat()
    row = (
        await session.execute(
            select(
                func.coalesce(func.sum(DailyStat.messages_count).filter(DailyStat.date >= today_s), 0),
                func.coalesce(func.sum(DailyStat.messages_count).filter(DailyStat.date >= week), 0),
                func.coalesce(func.sum(DailyStat.messages_count).filter(DailyStat.date >= month), 0),
                func.coalesce(func.sum(DailyStat.messages_count), 0),
                func.coalesce(func.sum(DailyStat.deleted_count), 0),
            ).where(DailyStat.group_id == group_id, DailyStat.user_telegram_id == user_id)
        )
    ).one()
    return tuple(int(value) for value in row)  # type: ignore[return-value]


async def _active_punishment(
    session: AsyncSession, group_id: int, user_id: int, kind: str
) -> Punishment | None:
    return await session.scalar(
        select(Punishment).where(
            Punishment.group_id == group_id,
            Punishment.user_telegram_id == user_id,
            Punishment.kind == kind,
            Punishment.active.is_(True),
        ).order_by(Punishment.created_at.desc())
    )


async def _profile_text(
    session: AsyncSession, group: Group, user_id: int, *, bot_id: int
) -> str:
    user_name = await _user_name(session, user_id)
    member = await session.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group.id,
            GroupMember.user_telegram_id == user_id,
        )
    )
    assignment = await session.scalar(
        select(RankAssignment).where(
            RankAssignment.group_id == group.id,
            RankAssignment.user_telegram_id == user_id,
            RankAssignment.active.is_(True),
        )
    )
    if user_id == bot_id:
        role = "Mimoru"
    elif group.owner_telegram_id == user_id:
        role = "Владелец"
    else:
        role = RANK_LABELS.get(assignment.rank_code, assignment.rank_code) if assignment else "Простой участник"

    ban = await _active_punishment(session, group.id, user_id, "ban")
    if ban is not None:
        status = "🚫 Забанен в чате"
    elif member is not None and member.is_present:
        status = "🕵️ Состоит в чате"
    else:
        status = "🚪 Покинул чат"

    day_count, week_count, month_count, all_count, deleted = await _message_periods(
        session, group.id, user_id
    )
    marriage = await _marriage_line(session, group.id, user_id)
    last_active = _ago_text(member.last_seen_at if member is not None else None)
    joined_date = member.joined_at if member is not None else None
    joined = "неизвестно" if joined_date is None else joined_date.astimezone(timezone.utc).strftime("%d.%m.%Y")
    joined_age = _membership_age(joined_date)

    return (
        f"👤 Это пользователь {user_name}\n"
        f"{status}\n"
        f"🧠 Роль: {role}\n"
        f"{marriage}\n"
        f"⌛ Последний актив: {last_active}\n\n"
        f"💬 Сообщения: {all_count}\n"
        "день | неделя | месяц | всего\n"
        f"{day_count} | {week_count} | {month_count} | {all_count}\n\n"
        f"🗑 Удалено: {_plural_messages(deleted)}\n"
        f"📅 В группе с: {joined} ({joined_age})"
    )


async def _history_text(session: AsyncSession, group: Group, user_id: int) -> str:
    label = await _user_name(session, user_id)
    active_warnings = int(
        await session.scalar(
            select(func.count()).select_from(Warning).where(
                Warning.group_id == group.id,
                Warning.user_telegram_id == user_id,
                Warning.active.is_(True),
            )
        )
        or 0
    )
    all_warnings = int(
        await session.scalar(
            select(func.count()).select_from(Warning).where(
                Warning.group_id == group.id,
                Warning.user_telegram_id == user_id,
            )
        )
        or 0
    )
    complaints = int(
        await session.scalar(
            select(func.count()).select_from(Complaint).where(
                Complaint.group_id == group.id,
                Complaint.target_telegram_id == user_id,
            )
        )
        or 0
    )
    mute = await _active_punishment(session, group.id, user_id, "mute")
    ban = await _active_punishment(session, group.id, user_id, "ban")

    def punishment_text(row: Punishment | None) -> str:
        if row is None:
            return "нет"
        if row.ends_at is None:
            return "да, без срока"
        return f"да, до {row.ends_at.astimezone(timezone.utc).strftime('%d.%m.%Y %H:%M UTC')}"

    return (
        f"⚖️ ИСТОРИЯ — {label}\n\n"
        f"⚠️ Предупреждения: {active_warnings} активных / {all_warnings} всего\n"
        f"🔇 Мут: {punishment_text(mute)}\n"
        f"🚫 Бан: {punishment_text(ban)}\n"
        f"🚨 Жалобы: {complaints}\n\n"
        "Статистика относится только к этой группе."
    )


async def _games_text(session: AsyncSession, group: Group, user_id: int) -> str:
    return await render_member_game_stats(
        session,
        group_id=group.id,
        user_id=user_id,
        label=await _user_name(session, user_id),
    )


async def _rp_text(session: AsyncSession, group: Group, user_id: int) -> str:
    label = await _user_name(session, user_id)
    rp_filter = (
        GameEvent.group_id == group.id,
        GameEvent.actor_telegram_id == user_id,
        GameEvent.event_type.in_(RP_EVENT_TYPES),
        or_(GameEvent.outcome.is_(None), GameEvent.outcome != "bot_wins"),
    )
    total = int(
        await session.scalar(
            select(func.count(GameEvent.id)).where(*rp_filter)
        )
        or 0
    )
    favorite_rows = (
        await session.execute(
            select(GameEvent.action, func.count(GameEvent.id))
            .where(*rp_filter, GameEvent.action.is_not(None))
            .group_by(GameEvent.action)
            .order_by(func.count(GameEvent.id).desc(), GameEvent.action)
            .limit(10)
        )
    ).all()

    lines = [
        f"🎭 РП — {label}",
        "",
        f"Всего использовано РП-действий: {total}",
        "",
        "Чаще всего используешь:",
    ]
    if favorite_rows:
        lines.extend(
            f"{index}. {action} — {int(count)}"
            for index, (action, count) in enumerate(favorite_rows, start=1)
        )
    else:
        lines.append("• пока нет РП-действий")
    lines.extend(["", "Здесь учитываются только РП/развлекательные действия в этой группе."])
    return "\n".join(lines)


async def _view_text(
    session: AsyncSession, group: Group, user_id: int, view: str, *, bot_id: int
) -> str:
    if view == "history":
        return await _history_text(session, group, user_id)
    if view == "games":
        return await _games_text(session, group, user_id)
    if view == "rp":
        return await _rp_text(session, group, user_id)
    return await _profile_text(session, group, user_id, bot_id=bot_id)


async def _send_profile(
    message: Message, bot: Bot, session: AsyncSession, group: Group, target_id: int
) -> None:
    if message.from_user is None:
        return
    text = await _profile_text(session, group, target_id, bot_id=bot.id)
    await message.reply(
        text,
        reply_markup=_profile_keyboard(group.id, target_id, message.from_user.id, "profile"),
    )


@router.message(F.chat.type.in_(GROUP_TYPES), F.reply_to_message, F.text.casefold().in_(LOOKUP_ALIASES))
async def lookup_profile(message: Message, bot: Bot, session: AsyncSession) -> None:
    if message.reply_to_message is None or message.reply_to_message.from_user is None:
        return
    group = await _active_group(session, message.chat.id)
    if group is None:
        return
    target = message.reply_to_message.from_user
    await upsert_user(session, target)
    await _send_profile(message, bot, session, group, target.id)


@router.message(F.chat.type.in_(GROUP_TYPES), F.text.casefold().in_(SELF_PROFILE_ALIASES))
async def own_profile(message: Message, bot: Bot, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    group = await _active_group(session, message.chat.id)
    if group is None:
        return
    await _send_profile(message, bot, session, group, message.from_user.id)


@router.callback_query(F.data.startswith("member_profile_v2:"))
async def profile_tab(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    parts = callback.data.split(":")
    if len(parts) != 5:
        await callback.answer("Карточка устарела. Откройте её заново.", show_alert=True)
        return
    _, raw_group_id, raw_target_id, raw_requester_id, view = parts
    try:
        group_id = int(raw_group_id)
        target_id = int(raw_target_id)
        requester_id = int(raw_requester_id)
    except ValueError:
        await callback.answer("Карточка устарела. Откройте её заново.", show_alert=True)
        return
    if callback.from_user.id != requester_id:
        await callback.answer(
            "Не для тебя мать кнопки прислала, отдыхай! Выпей лучше валерьянки и узбогойся...",
            show_alert=True,
        )
        return
    if view not in {"profile", "history", "games", "rp", "close"}:
        await callback.answer("Неизвестный раздел.", show_alert=True)
        return
    group = await session.scalar(select(Group).where(Group.id == group_id, Group.is_active.is_(True)))
    if group is None or callback.message.chat.id != group.telegram_chat_id:
        await callback.answer("Эта карточка больше недоступна.", show_alert=True)
        return

    if view == "close":
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            await callback.answer("Не удалось удалить карточку.", show_alert=True)
            return
        await callback.answer()
        return

    text = await _view_text(session, group, target_id, view, bot_id=bot.id)
    try:
        await callback.message.edit_text(
            text,
            reply_markup=_profile_keyboard(group.id, target_id, requester_id, view),
        )
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).casefold():
            raise
    await callback.answer()