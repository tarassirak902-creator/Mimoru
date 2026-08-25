from __future__ import annotations

import json
import secrets
import sys

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.panel import moderation_duration_picker, moderation_reason_picker
from app.services.access import can_moderate
from app.services.moderation_reasons import active_reasons
from app.services.permissions import target_is_protected
from app.services.public_identity import public_user_token
from app.services.repositories import get_or_create_group
from app.utils.commands import parse_command

router = Router(name=__name__)


def _replace_loaded_text(module_name: str, attribute: str, replacements: tuple[tuple[str, str], ...]) -> None:
    module = sys.modules.get(module_name)
    if module is None:
        return
    text = getattr(module, attribute, None)
    if not isinstance(text, str):
        return
    for old, new in replacements:
        text = text.replace(old, new)
    setattr(module, attribute, text)


def _retire_kick_from_legacy_help() -> None:
    """Remove kick instructions from the legacy secondary panel help.

    The active guided help is correct directly in source. Only the older panel
    module still needs compatibility sanitization while it remains registered.
    """
    _replace_loaded_text(
        "app.handlers.panel",
        "COMMANDS_TEXT",
        (
            (
                "<code>размут</code>, <code>кик</code>, <code>пред</code>, ",
                "<code>размут</code>, <code>пред</code>, ",
            ),
            (
                "Для предупреждения, мута, кика и бана Mimoru предложит причины кнопками.",
                "Для предупреждения, мута и бана Mimoru предложит причины кнопками.",
            ),
        ),
    )


_retire_kick_from_legacy_help()


@router.message(
    F.chat.type.in_({"group", "supergroup"}),
    F.reply_to_message,
    F.text.regexp(r"(?i)^(?:пред|мут|бан)(?:\s|$)"),
)
async def moderation_reason_entry(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    redis: Redis,
) -> None:
    """Require a configured reason before warn/mute/ban can execute.

    This router is intentionally registered before the legacy direct moderation
    handlers. The old path executed `пред`/`мут`/`бан` immediately and therefore
    bypassed the configured reason picker entirely.
    """
    if message.from_user is None or message.reply_to_message is None or message.reply_to_message.from_user is None:
        return
    command = parse_command(message.text or "")
    if command is None or command.action not in {"warn", "mute", "ban"}:
        return

    group = await get_or_create_group(session, message.chat, message.from_user.id)
    if not await can_moderate(bot, session, group, message.from_user.id, command.action):
        await message.reply("У вас нет права выполнять эту команду.")
        return

    target = message.reply_to_message.from_user
    if target.id == message.from_user.id:
        await message.reply("Нельзя применить эту команду к себе.")
        return
    if target.id == group.owner_telegram_id or await target_is_protected(bot, message.chat.id, target.id):
        await message.reply("Нельзя применить действие к владельцу или администратору Telegram.")
        return

    token = secrets.token_hex(5)
    payload = {
        "group_id": group.id,
        "chat_id": message.chat.id,
        "target_id": target.id,
        "target_name": public_user_token(target.id),
        "moderator_id": message.from_user.id,
        "moderator_name": public_user_token(message.from_user.id),
        "action": command.action,
        "duration": command.duration,
        "warnings_limit": group.settings.warnings_limit,
        "default_mute": group.settings.default_mute_seconds,
        "origin": "group",
        "actor_role": "owner" if message.from_user.id == group.owner_telegram_id else "admin",
    }
    key = f"mimoru:modpending:{token}"
    await redis.setex(key, 600, json.dumps(payload, ensure_ascii=False))

    if command.action == "mute" and command.duration is None:
        await message.reply(
            f"На сколько ограничить {public_user_token(target.id)}?",
            reply_markup=moderation_duration_picker(token),
        )
        return

    reasons = await active_reasons(session, group.id, command.action)
    await session.commit()
    if not reasons:
        await redis.delete(key)
        await message.reply(
            "Для этого действия нет активных причин. Владелец группы может добавить их в панели Mimoru."
        )
        return

    labels = {"warn": "предупреждения", "mute": "мута", "ban": "блокировки"}
    await message.reply(
        f"Выберите причину {labels[command.action]} для {public_user_token(target.id)}.",
        reply_markup=moderation_reason_picker(token, reasons),
    )


@router.callback_query(
    F.data.regexp(
        r"^(?:reason_action:\d+:\d+:kick|member_punish:\d+:-?\d+:kick|role_perm:\d+:\d+:kick)$"
    )
)
async def retired_kick_callback(callback: CallbackQuery) -> None:
    await callback.answer(
        "Кик отключён в Mimoru. Используйте предупреждение, мут или бан.",
        show_alert=True,
    )
