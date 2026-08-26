from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group, GroupSubscriptionEvent
from app.services.plans import effective_plan


async def apply_manual_plan(
    session: AsyncSession,
    *,
    group_id: int,
    actor_id: int,
    plan_code: str,
    days: int,
) -> Group | None:
    """Apply a manual plan change under the Group row lock and commit it atomically."""
    group = await session.scalar(
        select(Group).where(Group.id == group_id).with_for_update()
    )
    if group is None:
        return None

    now = datetime.now(timezone.utc)
    if plan_code == "free":
        group.plan_code = "free"
        group.plan_expires_at = None
    else:
        current_code = effective_plan(group)
        start = (
            group.plan_expires_at
            if current_code == plan_code and group.plan_expires_at and group.plan_expires_at > now
            else now
        )
        group.plan_code = plan_code
        group.plan_expires_at = start + timedelta(days=days)

    session.add(GroupSubscriptionEvent(
        group_id=group.id,
        actor_telegram_id=actor_id,
        event_type="admin_grant",
        plan_code=plan_code,
        expires_at=group.plan_expires_at,
    ))
    await session.commit()
    return group
