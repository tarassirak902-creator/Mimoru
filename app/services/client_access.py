from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group, User


@dataclass(frozen=True)
class ClientAccessResult:
    user: User
    disabled_groups: int


@dataclass(frozen=True)
class GroupServiceResult:
    group: Group | None
    blocked_owner: bool = False


async def set_client_blocked(
    session: AsyncSession,
    *,
    telegram_id: int,
    blocked: bool,
) -> ClientAccessResult | None:
    """Serialize client access changes with group ownership transfer.

    Group ownership transfer uses the same Group row lock. If transfer commits first,
    its row no longer matches this client's owner id; if blocking locks first, a later
    explicit reconnect can safely restore the transferred group's active state.
    """
    user = await session.scalar(
        select(User).where(User.telegram_id == telegram_id).with_for_update()
    )
    if user is None:
        return None

    disabled_groups = 0
    if blocked:
        groups = list((await session.scalars(
            select(Group)
            .where(Group.owner_telegram_id == telegram_id)
            .order_by(Group.id)
            .with_for_update()
        )).all())
        for group in groups:
            if group.is_active:
                group.is_active = False
                disabled_groups += 1

    user.service_blocked = blocked
    await session.commit()
    return ClientAccessResult(user=user, disabled_groups=disabled_groups)


async def set_group_service_active(
    session: AsyncSession,
    *,
    group_id: int,
    active: bool,
) -> GroupServiceResult:
    """Serialize service activation with client blocking and ownership transfer.

    The Group lock is intentionally acquired without a User row lock. Client blocking
    locks User -> Groups; taking User here after Group would invert that order. Under
    the Group lock the owner cannot change, so a fresh read of the current owner's
    blocked state is sufficient before activation.
    """
    group = await session.scalar(
        select(Group).where(Group.id == group_id).with_for_update()
    )
    if group is None:
        return GroupServiceResult(group=None)

    if active and group.owner_telegram_id is not None:
        blocked_owner = await session.scalar(
            select(User.service_blocked).where(User.telegram_id == group.owner_telegram_id)
        )
        if bool(blocked_owner):
            await session.commit()
            return GroupServiceResult(group=group, blocked_owner=True)

    group.is_active = active
    await session.commit()
    return GroupServiceResult(group=group)
