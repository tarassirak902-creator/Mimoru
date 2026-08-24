from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group
from app.services.access import is_service_owner


T = TypeVar("T")


async def mutate_setup_group(
    session: AsyncSession,
    *,
    group_id: int,
    actor_id: int,
    mutation: Callable[[Group], T],
) -> tuple[Group | None, T | None]:
    """Apply one setup-wizard mutation under the ownership-transfer lock."""
    group = await session.scalar(
        select(Group)
        .where(Group.id == group_id, Group.is_active.is_(True))
        .with_for_update()
    )
    if group is None:
        return None, None
    if actor_id != group.owner_telegram_id and not is_service_owner(actor_id):
        return None, None

    result = mutation(group)
    await session.commit()
    return group, result
