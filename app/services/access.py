from __future__ import annotations

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Group, GroupModerator

# Compatibility defaults for legacy handlers that still import this symbol.
# Runtime authorization is now based on app.services.ranks and rank_assignments.
DEFAULT_ROLE_PERMISSIONS = {
    "senior": {
        "ban": True, "unban": True, "mute": True, "unmute": True,
        "kick": False, "warn": True, "unwarn": True, "warnings": True,
        "info": True, "history": True, "delete": True,
    },
    "moderator": {
        "ban": False, "unban": False, "mute": True, "unmute": True,
        "kick": False, "warn": True, "unwarn": True, "warnings": True,
        "info": True, "history": True, "delete": True,
    },
    "helper": {
        "ban": False, "unban": False, "mute": False, "unmute": False,
        "kick": False, "warn": True, "unwarn": False, "warnings": True,
        "info": True, "history": True, "delete": False,
    },
}


def is_service_owner(user_id: int) -> bool:
    return user_id in get_settings().service_owner_ids


async def is_telegram_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
    except (TelegramBadRequest, TelegramForbiddenError):
        return False
    return member.status in {ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR}


async def is_group_owner(group: Group, user_id: int) -> bool:
    return group.owner_telegram_id == user_id or is_service_owner(user_id)


async def get_internal_moderator(
    session: AsyncSession,
    group_id: int,
    user_id: int,
) -> GroupModerator | None:
    """Compatibility lookup for legacy code.

    New authorization must use rank_assignments through app.services.ranks.
    """
    return await session.scalar(
        select(GroupModerator).where(
            GroupModerator.group_id == group_id,
            GroupModerator.user_telegram_id == user_id,
            GroupModerator.active.is_(True),
        )
    )


async def can_moderate(
    bot: Bot,
    session: AsyncSession,
    group: Group,
    user_id: int,
    action: str,
) -> bool:
    # Kick was retired from Mimoru's moderation surface. Keep this deny before
    # owner/service-owner shortcuts so stale callbacks or cached payloads cannot
    # revive the action.
    if action == "kick":
        return False
    from app.services.rank_access import can_use_rank_permission

    return await can_use_rank_permission(bot, session, group, user_id, action)


async def can_manage_group(bot: Bot, group: Group, user_id: int, session: AsyncSession | None = None) -> bool:
    if is_service_owner(user_id):
        return True
    if group.owner_telegram_id == user_id:
        return await is_telegram_admin(bot, group.telegram_chat_id, user_id)
    if session is None:
        return False
    from app.services.rank_access import get_actor_rank_with_access

    actor = await get_actor_rank_with_access(bot, session, group, user_id)
    return bool(actor is not None and actor.code == "deputy_owner")
