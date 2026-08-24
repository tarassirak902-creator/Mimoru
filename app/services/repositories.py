from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group, GroupSettings, User, UserProfileHistory, Warning


class GroupNotConnectedError(RuntimeError):
    """Raised when a group command is used before the creator connects the group."""


class GroupOwnerServiceBlockedError(RuntimeError):
    """Raised when a service-blocked creator tries to connect or reclaim a group."""


async def upsert_user(session: AsyncSession, tg_user) -> User:
    new_first = tg_user.first_name or ""
    existing = await session.scalar(select(User).where(User.telegram_id == tg_user.id))
    if existing is not None:
        if (existing.username, existing.first_name, existing.last_name) != (
            tg_user.username,
            new_first,
            tg_user.last_name,
        ):
            session.add(
                UserProfileHistory(
                    user_telegram_id=existing.telegram_id,
                    username=existing.username,
                    first_name=existing.first_name or "",
                    last_name=existing.last_name,
                )
            )

    stmt = pg_insert(User).values(
        telegram_id=tg_user.id,
        username=tg_user.username,
        first_name=new_first,
        last_name=tg_user.last_name,
        service_blocked=False,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[User.telegram_id],
        set_={
            "username": stmt.excluded.username,
            "first_name": stmt.excluded.first_name,
            "last_name": stmt.excluded.last_name,
        },
    )
    await session.execute(stmt)
    await session.flush()
    return await session.scalar(select(User).where(User.telegram_id == tg_user.id))


async def _invalidate_marketplace_on_owner_change(
    session: AsyncSession,
    group: Group,
    new_owner_id: int,
) -> None:
    """Retire seller authority before assigning a different group owner."""
    if group.owner_telegram_id == new_owner_id:
        return

    # Marketplace tables use a separately ensured runtime schema. Import them
    # only on the explicit ownership-transfer path so generic repository imports
    # do not mutate Base.metadata used by migration-consistency checks.
    from app.db.ad_market_models import RequiredAdDealRequest, RequiredAdListing

    # Serialize ownership changes with marketplace invalidation so no reconnect
    # can leave an active listing attached to the former owner.
    await session.scalar(
        select(Group).where(Group.id == group.id).with_for_update()
    )
    listing = await session.scalar(
        select(RequiredAdListing)
        .where(RequiredAdListing.seller_group_id == group.id)
        .with_for_update()
    )
    if listing is not None:
        listing.active = False
        pending = list((await session.scalars(
            select(RequiredAdDealRequest)
            .where(
                RequiredAdDealRequest.listing_id == listing.id,
                RequiredAdDealRequest.status == "pending",
            )
            .with_for_update()
        )).all())
        now = datetime.now(timezone.utc)
        for deal in pending:
            deal.status = "cancelled"
            deal.decided_at = now

    group.owner_telegram_id = new_owner_id


async def get_or_create_group(
    session: AsyncSession,
    chat,
    owner_id: int | None = None,
    *,
    create: bool = False,
) -> Group:
    # Explicit connect/reconnect must serialize with service blocking even when
    # the Group row does not exist yet. set_client_blocked() uses the same
    # User -> Group lock order, so holding the proposed owner row first makes a
    # first-time connect race deterministic without introducing lock inversion.
    if create and owner_id is not None:
        owner = await session.scalar(
            select(User).where(User.telegram_id == owner_id).with_for_update()
        )
        if owner is None:
            raise GroupOwnerServiceBlockedError("Владелец группы не зарегистрирован")
        if owner.service_blocked:
            raise GroupOwnerServiceBlockedError("Клиент заблокирован в Mimoru")

    query = select(Group).where(Group.telegram_chat_id == chat.id)
    if create:
        query = query.with_for_update()
    group = await session.scalar(query)
    if group is None:
        if not create:
            raise GroupNotConnectedError("Группа ещё не подключена к Mimoru")
        group = Group(
            telegram_chat_id=chat.id,
            title=chat.title or str(chat.id),
            owner_telegram_id=owner_id,
            plan_code="trial",
            plan_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        group.settings = GroupSettings()
        session.add(group)
        await session.flush()
    else:
        group.title = chat.title or group.title
        if not group.is_active and not create:
            raise GroupNotConnectedError("Группа отключена от Mimoru")
        if create:
            if owner_id:
                # Only the explicit connect flow may establish or restore ownership.
                # The proposed owner has already been locked and checked above.
                await _invalidate_marketplace_on_owner_change(session, group, owner_id)
            group.is_active = True
    return group


async def active_warnings_count(session: AsyncSession, group_id: int, user_id: int) -> int:
    value = await session.scalar(
        select(func.count())
        .select_from(Warning)
        .where(
            Warning.group_id == group_id,
            Warning.user_telegram_id == user_id,
            Warning.active.is_(True),
        )
    )
    return int(value or 0)