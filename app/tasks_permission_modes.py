from __future__ import annotations

from datetime import datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy import select

from app.db.models import Group, GroupSettings
from app.db.session import SessionFactory
from app.services.chat_permission_transitions import (
    LOCKED,
    apply_permission_transition,
    permissions_dict,
    permissions_from_dict,
    recover_chat_permission_transitions,
)
from app.services.night_mode import is_night_window, parse_hhmm
from app.services.timezones import to_local


async def _current_permissions(bot: Bot, chat_id: int) -> dict | None:
    try:
        chat = await bot.get_chat(chat_id)
    except (TelegramBadRequest, TelegramForbiddenError):
        return None
    return permissions_dict(chat.permissions)


async def expire_lockdowns(bot: Bot) -> None:
    await recover_chat_permission_transitions(bot)
    now = datetime.now(timezone.utc)
    async with SessionFactory() as session:
        group_ids = list((await session.scalars(
            select(Group.id)
            .join(GroupSettings, Group.settings)
            .where(
                Group.is_active.is_(True),
                GroupSettings.lockdown_enabled.is_(True),
                GroupSettings.lockdown_until.is_not(None),
                GroupSettings.lockdown_until <= now,
            )
        )).all())

    for group_id in group_ids:
        async with SessionFactory() as session:
            group = await session.scalar(
                select(Group)
                .where(Group.id == group_id, Group.is_active.is_(True))
                .with_for_update()
            )
            if (
                group is None
                or not group.settings.lockdown_enabled
                or group.settings.lockdown_until is None
                or group.settings.lockdown_until > now
            ):
                continue
            current = await _current_permissions(bot, group.telegram_chat_id)
            if current is None:
                continue
            desired = permissions_from_dict(group.settings.lockdown_previous_permissions)
            await apply_permission_transition(
                bot,
                session,
                group,
                operation="lockdown_off",
                desired_permissions=desired,
                previous_permissions=current,
                payload={"automatic": True},
            )


async def apply_night_modes(bot: Bot) -> None:
    await recover_chat_permission_transitions(bot)
    now = datetime.now(timezone.utc)
    async with SessionFactory() as session:
        group_ids = list((await session.scalars(
            select(Group.id).where(Group.is_active.is_(True))
        )).all())

    for group_id in group_ids:
        async with SessionFactory() as session:
            group = await session.scalar(
                select(Group)
                .where(Group.id == group_id, Group.is_active.is_(True))
                .with_for_update()
            )
            if group is None:
                continue
            settings = group.settings
            if not settings.night_mode_enabled and not settings.night_mode_active:
                continue
            local_now = to_local(now, settings.timezone_name)
            should_lock = settings.night_mode_enabled and is_night_window(
                local_now.time().replace(tzinfo=None),
                parse_hhmm(settings.night_mode_start),
                parse_hhmm(settings.night_mode_end),
            )

            if should_lock and not settings.night_mode_active and not settings.lockdown_enabled:
                current = await _current_permissions(bot, group.telegram_chat_id)
                if current is None:
                    continue
                await apply_permission_transition(
                    bot,
                    session,
                    group,
                    operation="night_lock",
                    desired_permissions=LOCKED,
                    previous_permissions=current,
                    payload={"automatic": True},
                )
                continue

            if not should_lock and settings.night_mode_active:
                if settings.lockdown_enabled:
                    settings.night_mode_active = False
                    settings.night_mode_previous_permissions = None
                    await session.commit()
                    continue
                current = await _current_permissions(bot, group.telegram_chat_id)
                if current is None:
                    continue
                desired = permissions_from_dict(settings.night_mode_previous_permissions)
                await apply_permission_transition(
                    bot,
                    session,
                    group,
                    operation="night_unlock",
                    desired_permissions=desired,
                    previous_permissions=current,
                    payload={"automatic": True},
                )
