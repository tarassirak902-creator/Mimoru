from __future__ import annotations

from datetime import datetime, timezone

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import ChatPermissions
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group
from app.db.permission_transition_models import ChatPermissionTransition
from app.db.session import SessionFactory
from app.services.access import is_service_owner
from app.services.night_mode import is_night_window, parse_hhmm
from app.services.timezones import to_local


LOCKED = ChatPermissions(can_send_messages=False)
OPEN = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_invite_users=True,
)


def permissions_dict(value: ChatPermissions | None) -> dict:
    if value is None:
        return {}
    return value.model_dump(exclude_none=True)


def permissions_from_dict(value: dict | None) -> ChatPermissions:
    return ChatPermissions(**value) if value else OPEN


def permissions_match(actual: ChatPermissions | None, expected: dict | None) -> bool:
    expected = expected or {}
    actual_data = permissions_dict(actual)
    return all(bool(actual_data.get(key, False)) == bool(value) for key, value in expected.items())


def _automatic_transition_is_current(
    group: Group,
    intent: ChatPermissionTransition,
    now: datetime,
) -> bool:
    if not (intent.payload or {}).get("automatic"):
        return True

    settings = group.settings
    if intent.operation == "lockdown_off":
        return bool(
            settings.lockdown_enabled
            and settings.lockdown_until is not None
            and settings.lockdown_until <= now
        )

    local_now = to_local(now, settings.timezone_name)
    should_lock = bool(
        settings.night_mode_enabled
        and is_night_window(
            local_now.time().replace(tzinfo=None),
            parse_hhmm(settings.night_mode_start),
            parse_hhmm(settings.night_mode_end),
        )
    )
    if intent.operation == "night_lock":
        return bool(
            should_lock
            and not settings.night_mode_active
            and not settings.lockdown_enabled
        )
    if intent.operation == "night_unlock":
        return bool(
            settings.night_mode_active
            and not settings.lockdown_enabled
            and not should_lock
        )
    return True


async def _finalize(
    session: AsyncSession,
    group: Group,
    intent: ChatPermissionTransition,
) -> None:
    settings = group.settings
    if intent.operation == "lockdown_on":
        settings.lockdown_enabled = True
        raw_until = (intent.payload or {}).get("until")
        settings.lockdown_until = datetime.fromisoformat(raw_until) if raw_until else None
        settings.lockdown_previous_permissions = intent.previous_permissions
        if (intent.payload or {}).get("clear_night"):
            settings.night_mode_active = False
            settings.night_mode_previous_permissions = None
    elif intent.operation == "lockdown_off":
        settings.lockdown_enabled = False
        settings.lockdown_until = None
        settings.lockdown_previous_permissions = None
    elif intent.operation == "night_lock":
        settings.night_mode_active = True
        settings.night_mode_previous_permissions = intent.previous_permissions
    elif intent.operation == "night_unlock":
        settings.night_mode_active = False
        settings.night_mode_previous_permissions = None
    else:
        raise ValueError(f"Unknown chat permission transition: {intent.operation}")
    await session.delete(intent)
    await session.commit()


async def _execute_live_transition(
    bot: Bot,
    session: AsyncSession,
    *,
    intent_id: int,
    actor_id: int | None,
) -> tuple[bool, str]:
    group_id = await session.scalar(
        select(ChatPermissionTransition.group_id).where(ChatPermissionTransition.id == intent_id)
    )
    if group_id is None:
        return False, "Изменение режима доступа больше не ожидает выполнения."

    group = await session.scalar(
        select(Group).where(Group.id == group_id).with_for_update()
    )
    intent = await session.scalar(
        select(ChatPermissionTransition)
        .where(ChatPermissionTransition.id == intent_id)
        .with_for_update()
    )
    if group is None or intent is None:
        return False, "Группа или изменение режима доступа больше не доступны."
    if not group.is_active:
        await session.delete(intent)
        await session.commit()
        return False, "Группа неактивна. Изменение режима отменено."
    if actor_id is not None and actor_id != group.owner_telegram_id and not is_service_owner(actor_id):
        await session.delete(intent)
        await session.commit()
        return False, "Права на группу изменились. Изменение режима отменено."
    if not _automatic_transition_is_current(group, intent, datetime.now(timezone.utc)):
        await session.delete(intent)
        await session.commit()
        return False, "Автоматическое изменение режима устарело и отменено."

    desired_permissions = permissions_from_dict(intent.desired_permissions)
    try:
        await bot.set_chat_permissions(group.telegram_chat_id, desired_permissions)
    except (TelegramBadRequest, TelegramForbiddenError) as error:
        structlog.get_logger().warning(
            "chat_permission_transition_failed",
            group_id=group.id,
            operation=intent.operation,
            error=str(error),
        )
        # The durable intent was committed before this execution transaction.
        # Keep it for reconcile-only recovery, but release the ownership row lock.
        await session.commit()
        return False, "Telegram не применил права. Состояние сохранено для безопасного повтора."

    await _finalize(session, group, intent)
    return True, ""


async def apply_permission_transition(
    bot: Bot,
    session: AsyncSession,
    group: Group,
    *,
    operation: str,
    desired_permissions: ChatPermissions,
    previous_permissions: dict | None,
    actor_id: int | None = None,
    payload: dict | None = None,
) -> tuple[bool, str]:
    existing = await session.scalar(
        select(ChatPermissionTransition).where(ChatPermissionTransition.group_id == group.id)
    )
    if existing is not None:
        return False, "Для группы уже выполняется изменение режима доступа. Повторите позже."

    intent = ChatPermissionTransition(
        group_id=group.id,
        operation=operation,
        previous_permissions=previous_permissions,
        desired_permissions=permissions_dict(desired_permissions),
        payload=payload or {},
    )
    session.add(intent)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return False, "Для группы уже выполняется изменение режима доступа."

    return await _execute_live_transition(
        bot,
        session,
        intent_id=intent.id,
        actor_id=actor_id,
    )


async def recover_chat_permission_transitions(bot: Bot) -> None:
    """Reconcile durable permission intents against current serialized group state."""
    log = structlog.get_logger()
    async with SessionFactory() as session:
        ids = list((await session.scalars(select(ChatPermissionTransition.id))).all())

    for intent_id in ids:
        async with SessionFactory() as session:
            group_id = await session.scalar(
                select(ChatPermissionTransition.group_id).where(
                    ChatPermissionTransition.id == intent_id
                )
            )
            if group_id is None:
                continue

            group = await session.scalar(
                select(Group).where(Group.id == group_id).with_for_update()
            )
            intent = await session.scalar(
                select(ChatPermissionTransition)
                .where(ChatPermissionTransition.id == intent_id)
                .with_for_update()
            )
            if intent is None:
                continue
            if group is None or not group.is_active:
                await session.delete(intent)
                await session.commit()
                continue

            if not _automatic_transition_is_current(group, intent, datetime.now(timezone.utc)):
                await session.delete(intent)
                await session.commit()
                log.info(
                    "chat_permission_transition_recovery_stale",
                    intent_id=intent_id,
                    group_id=group.id,
                    operation=intent.operation,
                )
                continue

            try:
                chat = await bot.get_chat(group.telegram_chat_id)
            except (TelegramBadRequest, TelegramForbiddenError) as error:
                log.warning(
                    "chat_permission_recovery_read_failed",
                    intent_id=intent.id,
                    group_id=group.id,
                    error=str(error),
                )
                continue

            if permissions_match(chat.permissions, intent.desired_permissions):
                await _finalize(session, group, intent)
                log.info(
                    "chat_permission_transition_recovered",
                    intent_id=intent_id,
                    group_id=group.id,
                    operation=intent.operation,
                )
                continue

            if permissions_match(chat.permissions, intent.previous_permissions):
                await session.delete(intent)
                await session.commit()
                log.info(
                    "chat_permission_transition_not_applied",
                    intent_id=intent_id,
                    group_id=group.id,
                    operation=intent.operation,
                )
                continue

            log.warning(
                "chat_permission_transition_ambiguous",
                intent_id=intent.id,
                group_id=group.id,
                operation=intent.operation,
            )
