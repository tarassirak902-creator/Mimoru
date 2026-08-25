from __future__ import annotations

import json
import re
import secrets

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group, GroupMember, User
from app.db.moderation_command_models import ModerationCommandPreference
from app.keyboards.panel import moderation_duration_picker, moderation_reason_picker
from app.services.access import can_moderate, is_service_owner
from app.services.moderation import execute
from app.services.moderation_reasons import active_reasons
from app.services.permissions import target_is_protected
from app.services.public_identity import public_user_token
from app.services.ranks import can_moderate_target
from app.services.ui import panel_header
from app.utils.duration import parse_duration


router = Router(name=__name__)
GROUP_TYPES = {"group", "supergroup"}
COMMAND_RE = re.compile(r"(?is)^(пред|мут|бан)(?:\s|$)")
VALID_MODES = {"buttons", "text", "both"}
MODE_LABELS = {
    "buttons": "🔘 Кнопки",
    "text": "📝 Текстовый",
    "both": "✅ Оба режима",
}


async def _active_group(session: AsyncSession, chat_id: int) -> Group | None:
    return await session.scalar(
        select(Group).where(Group.telegram_chat_id == chat_id, Group.is_active.is_(True))
    )


async def _owned_group(session: AsyncSession, group_id: int, user_id: int) -> Group | None:
    query = select(Group).where(Group.id == group_id, Group.is_active.is_(True))
    if not is_service_owner(user_id):
        query = query.where(Group.owner_telegram_id == user_id)
    return await session.scalar(query)


async def _preference(session: AsyncSession, group_id: int) -> ModerationCommandPreference:
    row = await session.get(ModerationCommandPreference, group_id)
    if row is None:
        row = ModerationCommandPreference(group_id=group_id, mode="both")
        session.add(row)
        await session.flush()
    if row.mode not in VALID_MODES:
        row.mode = "both"
    return row


def _moderation_menu(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚩 Жалобы", callback_data=f"complaints:{group_id}")],
        [InlineKeyboardButton(text="📌 Причины наказаний", callback_data=f"reasons:{group_id}")],
        [InlineKeyboardButton(text="🔇 Мут по умолчанию", callback_data=f"setting_num:{group_id}:defaultmute")],
        [InlineKeyboardButton(text="⌨️ Режим админ-команд", callback_data=f"modcmd_mode:{group_id}")],
        [
            InlineKeyboardButton(text="👮 Модераторы", callback_data=f"roles:{group_id}"),
            InlineKeyboardButton(text="📋 Журнал", callback_data=f"logs:{group_id}"),
        ],
        [InlineKeyboardButton(text="ℹ️ Как модерировать", callback_data=f"moderation_help:{group_id}")],
        [InlineKeyboardButton(text="◀️ Назад к группе", callback_data=f"group:{group_id}")],
    ])


@router.callback_query(F.data.regexp(r"^group_section:\d+:moderation$"))
async def moderation_section(callback: CallbackQuery, session: AsyncSession) -> None:
    _, raw_group, _ = callback.data.split(":")
    group = await _owned_group(session, int(raw_group), callback.from_user.id)
    if group is None:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.message.edit_text(
        panel_header("Модерация", "Наказания, причины, роли и режим админ-команд"),
        reply_markup=_moderation_menu(group.id),
    )
    await callback.answer()


def _mode_keyboard(group_id: int, current: str) -> InlineKeyboardMarkup:
    def button(mode: str) -> InlineKeyboardButton:
        marker = "✅ " if mode == current else "▫️ "
        return InlineKeyboardButton(
            text=marker + MODE_LABELS[mode].split(" ", 1)[1],
            callback_data=f"modcmd_set:{group_id}:{mode}",
        )

    return InlineKeyboardMarkup(inline_keyboard=[
        [button("text")],
        [button("buttons")],
        [button("both")],
        [InlineKeyboardButton(text="◀️ Модерация", callback_data=f"group_section:{group_id}:moderation")],
    ])


async def _render_mode(callback: CallbackQuery, session: AsyncSession, group: Group) -> None:
    pref = await _preference(session, group.id)
    await session.commit()
    text = panel_header(
        "Режим админ-команд",
        "Выберите, как работают команды пред / мут / бан.\n\n"
        "🔘 Кнопки — укажите пользователя ответом, @username или Telegram ID; Mimoru предложит срок/причину кнопками.\n\n"
        "📝 Текстовый — причина пишется со второй строки, и действие выполняется сразу без кнопок.\n\n"
        "✅ Оба режима — если есть причина со второй строки, действие выполняется сразу; если её нет, открываются кнопки.",
    )
    await callback.message.edit_text(text, reply_markup=_mode_keyboard(group.id, pref.mode))


@router.callback_query(F.data.regexp(r"^modcmd_mode:\d+$"))
async def moderation_mode(callback: CallbackQuery, session: AsyncSession) -> None:
    group = await _owned_group(session, int(callback.data.split(":")[-1]), callback.from_user.id)
    if group is None:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await _render_mode(callback, session, group)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^modcmd_set:\d+:(buttons|text|both)$"))
async def moderation_mode_set(callback: CallbackQuery, session: AsyncSession) -> None:
    _, raw_group, mode = callback.data.split(":")
    group = await _owned_group(session, int(raw_group), callback.from_user.id)
    if group is None:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    pref = await _preference(session, group.id)
    pref.mode = mode
    await session.commit()
    await _render_mode(callback, session, group)
    await callback.answer("Режим сохранён")


async def _username_target(session: AsyncSession, group_id: int, raw: str) -> int | None:
    username = raw.lstrip("@").casefold()
    return await session.scalar(
        select(User.telegram_id)
        .join(GroupMember, GroupMember.user_telegram_id == User.telegram_id)
        .where(GroupMember.group_id == group_id, func.lower(User.username) == username)
        .limit(1)
    )


def _split_command(text: str) -> tuple[str, list[str], str]:
    lines = text.replace("\r\n", "\n").split("\n")
    first = lines[0].strip()
    parts = first.split()
    command = parts[0].casefold()
    reason = "\n".join(lines[1:]).strip()
    return command, parts[1:], reason


async def _parse_target_and_duration(
    session: AsyncSession,
    group: Group,
    message: Message,
    args: list[str],
) -> tuple[int | None, int | None, str | None]:
    target_id = None
    if message.reply_to_message is not None and message.reply_to_message.from_user is not None:
        target_id = message.reply_to_message.from_user.id

    duration = None
    unknown: list[str] = []
    for token in args:
        parsed_duration = parse_duration(token)
        if parsed_duration is not None and duration is None:
            duration = parsed_duration
            continue
        if target_id is None and token.isdigit():
            target_id = int(token)
            continue
        if target_id is None and token.startswith("@"):
            resolved = await _username_target(session, group.id, token)
            if resolved is None:
                return None, duration, f"Пользователь {token} не найден среди известных участников группы."
            target_id = int(resolved)
            continue
        unknown.append(token)

    if unknown:
        return None, duration, (
            "Не удалось разобрать команду. В первой строке оставьте только команду, пользователя и срок. "
            "Причину пишите со второй строки."
        )
    if target_id is None:
        return None, duration, "Укажите пользователя: ответом на сообщение, @username или Telegram ID."
    return target_id, duration, None


async def _check_target(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    group: Group,
    target_id: int,
) -> str | None:
    if message.from_user is None:
        return "Не удалось определить модератора."
    if target_id == message.from_user.id:
        return "Нельзя применить эту команду к себе."
    if target_id == group.owner_telegram_id:
        return "Нельзя применить действие к владельцу группы."
    allowed, reason = await can_moderate_target(session, group, message.from_user.id, target_id)
    if not allowed:
        return reason
    try:
        if await target_is_protected(bot, message.chat.id, target_id):
            return "Нельзя применить действие к защищённому администратору Telegram."
    except (TelegramBadRequest, TelegramForbiddenError):
        pass
    return None


async def _open_buttons(
    message: Message,
    redis: Redis,
    session: AsyncSession,
    group: Group,
    *,
    action: str,
    target_id: int,
    duration: int | None,
) -> None:
    token = secrets.token_hex(5)
    payload = {
        "group_id": group.id,
        "chat_id": message.chat.id,
        "target_id": target_id,
        "target_name": public_user_token(target_id),
        "moderator_id": message.from_user.id,
        "moderator_name": public_user_token(message.from_user.id),
        "action": action,
        "duration": duration,
        "warnings_limit": group.settings.warnings_limit,
        "default_mute": group.settings.default_mute_seconds,
        "origin": "group",
        "actor_role": "owner" if message.from_user.id == group.owner_telegram_id else "admin",
    }
    await redis.setex(f"mimoru:modpending:{token}", 600, json.dumps(payload, ensure_ascii=False))
    if action == "mute" and duration is None:
        await message.reply(
            f"🔇 На сколько ограничить {public_user_token(target_id)}?",
            reply_markup=moderation_duration_picker(token),
        )
        return
    reasons = await active_reasons(session, group.id, action)
    if not reasons:
        await redis.delete(f"mimoru:modpending:{token}")
        await message.reply("Для этого действия нет активных причин. Владелец группы может добавить их в панели Mimoru.")
        return
    labels = {"warn": "предупреждения", "mute": "мута", "ban": "блокировки"}
    await message.reply(
        f"📌 Выберите причину {labels[action]} для {public_user_token(target_id)}.",
        reply_markup=moderation_reason_picker(token, reasons),
    )


@router.message(F.chat.type.in_(GROUP_TYPES), F.text.regexp(COMMAND_RE))
async def moderation_command_mode(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    redis: Redis,
) -> None:
    if message.from_user is None:
        return
    group = await _active_group(session, message.chat.id)
    if group is None:
        return

    command_word, args, direct_reason = _split_command(message.text or "")
    action = {"пред": "warn", "мут": "mute", "бан": "ban"}.get(command_word)
    if action is None:
        return
    if not await can_moderate(bot, session, group, message.from_user.id, action):
        await message.reply("У вас нет права выполнять эту команду.")
        return

    target_id, duration, error = await _parse_target_and_duration(session, group, message, args)
    if error or target_id is None:
        await message.reply(error or "Не удалось определить пользователя.")
        return
    if action == "warn" and duration is not None:
        await message.reply("Для предупреждения срок не указывается.")
        return

    target_error = await _check_target(message, bot, session, group, target_id)
    if target_error:
        await message.reply(target_error)
        return

    pref = await _preference(session, group.id)
    mode = pref.mode
    await session.commit()

    use_direct = bool(direct_reason) and mode in {"text", "both"}
    if mode == "text" and not direct_reason:
        await message.reply(
            "Включён текстовый режим. Причину напишите со второй строки.\n\n"
            "Примеры:\n"
            "пред @username\nСпам\n\n"
            "мут 123456 2ч\nОскорбления\n\n"
            "Или ответьте на сообщение:\nбан\nПовторное нарушение"
        )
        return

    if use_direct:
        try:
            result = await execute(
                bot=bot,
                session=session,
                chat_id=message.chat.id,
                group_id=group.id,
                target_id=target_id,
                moderator_id=message.from_user.id,
                action=action,
                duration=duration,
                reason=direct_reason[:1000],
                warnings_limit=group.settings.warnings_limit,
                default_mute=group.settings.default_mute_seconds,
                target_name=public_user_token(target_id),
                moderator_name=public_user_token(message.from_user.id),
                actor_role="owner" if message.from_user.id == group.owner_telegram_id else "admin",
            )
            await session.commit()
            await message.reply(result)
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            await session.rollback()
            await message.reply(f"Не удалось выполнить действие: {exc.message}")
        return

    await _open_buttons(
        message,
        redis,
        session,
        group,
        action=action,
        target_id=target_id,
        duration=duration,
    )
