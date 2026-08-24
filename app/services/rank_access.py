from __future__ import annotations

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group
from app.services.access import is_telegram_admin
from app.services.ranks import ActorRank, actor_has_permission, get_actor_rank


async def get_actor_rank_with_access(
    bot: Bot,
    session: AsyncSession,
    group: Group,
    user_id: int,
) -> ActorRank | None:
    """Resolve an actor only while the assignment's access mode is valid."""
    actor = await get_actor_rank(session, group, user_id)
    if actor is None:
        return None
    if actor.level >= 100:
        return actor
    assignment = actor.assignment
    if assignment is None:
        return None

    mode = getattr(assignment, "access_mode", "bot_only")
    if mode == "bot_only":
        return actor
    if mode == "telegram":
        if await is_telegram_admin(bot, group.telegram_chat_id, user_id):
            return actor
        return None
    return None


async def can_use_rank_permission(
    bot: Bot,
    session: AsyncSession,
    group: Group,
    user_id: int,
    permission: str,
) -> bool:
    actor = await get_actor_rank_with_access(bot, session, group, user_id)
    if actor is None:
        return False
    if actor.level >= 100:
        return True
    return await actor_has_permission(session, group, user_id, permission)
