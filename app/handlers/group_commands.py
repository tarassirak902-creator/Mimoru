from __future__ import annotations

import re

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Complaint, Group, GroupMember, User, Warning
from app.db.rank_models import RankAssignment
from app.services.access import can_moderate
from app.services.moderation import execute, log_action
from app.services.public_identity import public_user_token
from app.services.ranks import (
    CHAT_ADMIN,
    CHIEF_ADMIN,
    DEPUTY_OWNER,
    HELPER,
    can_moderate_target,
    get_assignment,
)
from app.services.ui import panel_header
from app.utils.user_resolver import resolve_target_user


router = Router(name=__name__)
GROUP_TYPES = {"group", "supergroup"}
COMPLAINT_WORDS = {"жалоба", "доложить", "нарушитель"}
CLEAR_WARNING_WORDS = {
    "снять все предупреждения",
    "снять предупреждения",
    "обнулить предупреждения",
    "снять все преды",
}
DIRECT_MODERATION_RE = re.compile(r"^(?:мут|бан|пред|снять пред)(?:\s|$)", re.IGNORECASE)
DURATION_RE = re.compile(
    r"(?P<value>\d+)\s*(?P<unit>с|сек(?:унд(?:а|ы)?)?|м|мин(?:ут(?:а|ы)?)?|ч|час(?:а|ов)?|д|дн(?:я|ей)?)",
    re.IGNORECASE,
)


async def _active_group(
    session: AsyncSession,
    chat_id: int,
    *,
    for_update: bool = False,
) -> Group | None:
    query = select(Group).where(
        Group.telegram_chat_id == chat_id,
        Group.is_active.is_(True),
    )
    if for_update:
        query = query.with_for_update()
    return await session.scalar(query)


def _target_from_reply(message: Message):
    if message.reply_to_message is None:
        return None
    return message.reply_to_message.from_user


def parse_duration(text: str) -> int | None:
    match = DURATION_RE.search(text.casefold())
    if match is None:
        return None
    value = int(match.group("value"))
    unit = match.group("unit").casefold()
    if unit.startswith("с"):
        multiplier = 1
    elif unit == "м" or unit.startswith("мин"):
        multiplier = 60
    elif unit == "ч" or unit.startswith("час"):
        multiplier = 3600
    else:
        multiplier = 86400
    return value * multiplier


def _moderation_reason(raw: str, command_len: int, *, remove_duration: bool = False) -> str:
    """Return only a reason explicitly supplied by the moderator."""
    tail = raw[command_len:].strip()
    if remove_duration:
        tail = DURATION_RE.sub("", tail, count=1).strip(" \t\n,.;:-")
    return tail.strip()


async def _notify_complaint_recipients(
    bot: Bot,
    session: AsyncSession,
    group: Group,
    reporter_id: int,
    reporter_name: str,
    target_id: int,
    target_name: str,
    message_id: int,
) -> int:
    reporter_rank = await get_assignment(session, group.id, reporter_id)
    recipients: set[int] = set()
    if reporter_rank is not None and reporter_rank.rank_code == HELPER and reporter_rank.helper_for_telegram_id:
        recipients.add(reporter_rank.helper_for_telegram_id)
    else:
        if group.owner_telegram_id:
            recipients.add(group.owner_telegram_id)
        rows = (
            await session.scalars(
                select(RankAssignment.user_telegram_id).where(
                    RankAssignment.group_id == group.id,
                    RankAssignment.active.is_(True),
                    RankAssignment.rank_code.in_((DEPUTY_OWNER, CHIEF_ADMIN, CHAT_ADMIN)),
                )
            )
        ).all()
        recipients.update(int(value) for value in rows)

    recipients.discard(reporter_id)
    delivered = 0
    # Names are resolved centrally right before Telegram delivery. The old duplicated
    # "name · ID 123" output is intentionally gone: admins see one clickable identity.
    text = panel_header(
        "Жалоба в группе",
        f"Группа: {group.title}\n"
        f"Кто пожаловался: {public_user_token(reporter_id)}\n"
        f"На кого: {public_user_token(target_id)}\n"
        f"Сообщение: №{message_id}\n\n"
        "Проверьте ситуацию перед применением наказания.",
    )
    for recipient in recipients:
        try:
            await bot.send_message(recipient, text)
            delivered += 1
        except (TelegramBadRequest, TelegramForbiddenError):
            continue
    return delivered


@router.message(
    F.chat.type.in_(GROUP_TYPES),
    F.reply_to_message,
    F.text.casefold().in_(COMPLAINT_WORDS),
)
async def group_complaint(message: Message, bot: Bot, session: AsyncSession) -> None:
    target = _target_from_reply(message)
    if target is None or message.from_user is None:
        return
    if target.id == message.from_user.id:
        await message.reply("Нельзя отправить жалобу на самого себя.")
        return
    group = await _active_group(session, message.chat.id)
    if group is None:
        return

    existing = await session.scalar(
        select(Complaint.id).where(
            Complaint.group_id == group.id,
            Complaint.reporter_telegram_id == message.from_user.id,
            Complaint.message_id == message.reply_to_message.message_id,
            Complaint.status == "pending",
        )
    )
    if existing is not None:
        await message.reply("Эта жалоба уже отправлена и ожидает проверки.")
        return

    complaint = Complaint(
        group_id=group.id,
        reporter_telegram_id=message.from_user.id,
        target_telegram_id=target.id,
        message_id=message.reply_to_message.message_id,
        message_text=(message.reply_to_message.text or message.reply_to_message.caption or "")[:4000] or None,
        status="pending",
    )
    session.add(complaint)
    await session.flush()

    delivered = await _notify_complaint_recipients(
        bot,
        session,
        group,
        message.from_user.id,
        message.from_user.full_name or str(message.from_user.id),
        target.id,
        target.full_name or str(target.id),
        message.reply_to_message.message_id,
    )
    await session.commit()
    if delivered:
        await message.reply("✅ Жалоба принята. Администраторы группы получили уведомление.")
    else:
        await message.reply("✅ Жалоба сохранена. Сейчас не удалось доставить личное уведомление администраторам.")


async def _do_unmute(
    message: Message, bot: Bot, session: AsyncSession, *, target_id: int
) -> None:
    group = await _active_group(session, message.chat.id)
    if group is None:
        return
    if not await can_moderate(bot, session, group, message.from_user.id, "unmute"):
        return
    notice = await execute(
        bot=bot,
        session=session,
        chat_id=message.chat.id,
        group_id=group.id,
        target_id=target_id,
        moderator_id=message.from_user.id,
        action="unmute",
        duration=None,
        reason="",
        warnings_limit=group.settings.warnings_limit,
        default_mute=group.settings.default_mute_seconds,
        target_name=public_user_token(target_id),
        moderator_name=public_user_token(message.from_user.id),
    )
    await session.commit()
    await message.reply(notice)


async def _do_unban(
    message: Message, bot: Bot, session: AsyncSession, *, target_id: int
) -> None:
    group = await _active_group(session, message.chat.id)
    if group is None:
        return
    if not await can_moderate(bot, session, group, message.from_user.id, "unban"):
        return
    notice = await execute(
        bot=bot,
        session=session,
        chat_id=message.chat.id,
        group_id=group.id,
        target_id=target_id,
        moderator_id=message.from_user.id,
        action="unban",
        duration=None,
        reason="",
        warnings_limit=group.settings.warnings_limit,
        default_mute=group.settings.default_mute_seconds,
        target_name=public_user_token(target_id),
        moderator_name=public_user_token(message.from_user.id),
    )
    await session.commit()
    await message.reply(notice)


@router.message(
    F.chat.type.in_(GROUP_TYPES),
    F.text.casefold().in_({"говори", "размут", "размутить", "снять мут"}),
)
async def unmute_combined(message: Message, bot: Bot, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    target_id, label = await resolve_target_user(
        session, message.chat.id, message, command_keyword="говори",
    )
    if target_id is None:
        if message.reply_to_message is None:
            await message.reply(
                "Укажите пользователя: ответьте на его сообщение или напишите "
                "<code>размут @username</code> / <code>размут 123456</code>."
            )
        return
    await _do_unmute(message, bot, session, target_id=target_id)


@router.message(
    F.chat.type.in_(GROUP_TYPES),
    F.reply_to_message,
    F.text.casefold().in_(CLEAR_WARNING_WORDS),
)
async def clear_all_warnings(message: Message, bot: Bot, session: AsyncSession) -> None:
    target = _target_from_reply(message)
    if target is None or message.from_user is None:
        return
    group = await _active_group(session, message.chat.id, for_update=True)
    if group is None:
        return
    if not await can_moderate(bot, session, group, message.from_user.id, "unwarn"):
        return
    allowed, reason = await can_moderate_target(session, group, message.from_user.id, target.id)
    if not allowed:
        await message.reply(reason)
        return

    rows = list(
        (
            await session.scalars(
                select(Warning).where(
                    Warning.group_id == group.id,
                    Warning.user_telegram_id == target.id,
                    Warning.active.is_(True),
                )
            )
        ).all()
    )
    if not rows:
        await message.reply("У этого участника нет активных предупреждений.")
        return
    for row in rows:
        row.active = False
    log_action(
        session,
        group.id,
        message.from_user.id,
        target.id,
        "unwarn_all",
        "Сняты все предупреждения",
        {"count": len(rows)},
    )
    await session.commit()
    await message.reply(f"✅ Сняты все активные предупреждения: {len(rows)}.")


@router.message(
    F.chat.type.in_(GROUP_TYPES),
    F.reply_to_message,
    F.text.regexp(DIRECT_MODERATION_RE),
)
async def direct_reply_moderation(message: Message, bot: Bot, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    group = await _active_group(session, message.chat.id)
    if group is None:
        return

    raw = (message.text or "").strip()
    lowered = raw.casefold()
    action: str
    duration: int | None = None
    reason = ""

    if lowered == "снять пред" or lowered.startswith("снять пред "):
        action = "unwarn"
    elif lowered == "бан" or lowered.startswith("бан "):
        action = "ban"
        duration = parse_duration(raw[3:])
        reason = _moderation_reason(raw, 3, remove_duration=True)
    elif lowered == "мут" or lowered.startswith("мут "):
        action = "mute"
        duration = parse_duration(raw[3:])
        reason = _moderation_reason(raw, 3, remove_duration=True)
    elif lowered == "пред" or lowered.startswith("пред "):
        action = "warn"
        reason = _moderation_reason(raw, 4)
    else:
        return

    target_id, _ = await resolve_target_user(
        session, message.chat.id, message, command_keyword="",
    )
    if target_id is None:
        return
    if not await can_moderate(bot, session, group, message.from_user.id, action):
        return

    notice = await execute(
        bot=bot,
        session=session,
        chat_id=message.chat.id,
        group_id=group.id,
        target_id=target_id,
        moderator_id=message.from_user.id,
        action=action,
        duration=duration,
        reason=reason,
        warnings_limit=group.settings.warnings_limit,
        default_mute=group.settings.default_mute_seconds,
        target_name=public_user_token(target_id),
        moderator_name=public_user_token(message.from_user.id),
    )
    await session.commit()
    await message.reply(notice)


async def _resolve_group_user(session: AsyncSession, group_id: int, raw: str) -> tuple[int | None, str]:
    value = raw.strip()
    if value.isdigit():
        target_id = int(value)
        known = await session.scalar(
            select(GroupMember.id).where(
                GroupMember.group_id == group_id,
                GroupMember.user_telegram_id == target_id,
            )
        )
        return (target_id, public_user_token(target_id)) if known is not None else (None, value)
    if not value.startswith("@") or len(value) < 2:
        return None, value
    username = value[1:].casefold()
    row = await session.execute(
        select(User.telegram_id, User.username)
        .join(GroupMember, GroupMember.user_telegram_id == User.telegram_id)
        .where(
            GroupMember.group_id == group_id,
            func.lower(User.username) == username,
        )
        .limit(1)
    )
    found = row.first()
    if found is None:
        return None, value
    target_id = int(found.telegram_id)
    return target_id, public_user_token(target_id)


@router.message(
    F.chat.type.in_(GROUP_TYPES),
    F.text.casefold().in_({"разбан", "разбанить", "снять бан"}),
)
async def unban_combined(message: Message, bot: Bot, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    group = await _active_group(session, message.chat.id)
    if group is None:
        return
    if not await can_moderate(bot, session, group, message.from_user.id, "unban"):
        return

    target_id, target_label = await resolve_target_user(
        session, message.chat.id, message, command_keyword="разбан",
    )
    if target_id is None:
        if message.reply_to_message is None:
            await message.reply(
                "Укажите пользователя: ответьте на его сообщение или напишите "
                "<code>разбан @username</code> / <code>разбан 123456</code>."
            )
        return

    notice = await execute(
        bot=bot,
        session=session,
        chat_id=message.chat.id,
        group_id=group.id,
        target_id=target_id,
        moderator_id=message.from_user.id,
        action="unban",
        duration=None,
        reason="",
        warnings_limit=group.settings.warnings_limit,
        default_mute=group.settings.default_mute_seconds,
        target_name=target_label,
        moderator_name=public_user_token(message.from_user.id),
    )
    await session.commit()
    await message.reply(notice)
