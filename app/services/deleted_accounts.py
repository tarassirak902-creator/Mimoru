from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group, GroupMember, User
from app.services.repositories import upsert_user
from app.utils.telegram_users import is_deleted_profile


async def track_group_member(
    session: AsyncSession,
    group_id: int,
    tg_user,
    *,
    present: bool = True,
    checked: bool = False,
) -> GroupMember | None:
    if tg_user is None:
        return None
    await upsert_user(session, tg_user)
    now = datetime.now(timezone.utc)
    stmt = pg_insert(GroupMember).values(
        group_id=group_id,
        user_telegram_id=tg_user.id,
        is_present=present,
        is_deleted_account=is_deleted_profile(tg_user),
        last_seen_at=now,
        joined_at=now,
        last_checked_at=now if checked else None,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_group_members_group_user",
        set_={
            "is_present": stmt.excluded.is_present,
            "is_deleted_account": stmt.excluded.is_deleted_account,
            "last_seen_at": stmt.excluded.last_seen_at,
            "last_checked_at": now if checked else GroupMember.last_checked_at,
        },
    )
    await session.execute(stmt)
    await session.flush()
    return await session.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_telegram_id == tg_user.id,
        )
    )


async def mark_member_presence(
    session: AsyncSession,
    group_id: int,
    user_id: int,
    *,
    present: bool,
) -> None:
    row = await session.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_telegram_id == user_id,
        )
    )
    if row is not None:
        row.is_present = present
        row.last_checked_at = datetime.now(timezone.utc)
        await session.flush()


async def deleted_accounts_count(session: AsyncSession, group_id: int) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.is_present.is_(True),
                GroupMember.is_deleted_account.is_(True),
            )
        )
        or 0
    )


@dataclass(frozen=True)
class ScanResult:
    checked: int
    deleted: int
    present: int
    inaccessible: int


@dataclass(frozen=True)
class CleanupResult:
    found: int
    removed: int
    failed: int


async def _telegram_call(call):
    while True:
        try:
            return await call()
        except TelegramRetryAfter as exc:
            await asyncio.sleep(float(exc.retry_after) + 0.2)


async def scan_known_members(bot: Bot, session: AsyncSession, group: Group) -> ScanResult:
    """Refresh deleted-account state for members already known to Mimoru.

    Telegram Bot API cannot enumerate every member of an arbitrary group.
    Therefore the scan covers IDs Mimoru has observed via messages, joins or
    chat-member updates. The UI explicitly discloses this limitation.

    This function releases the DB connection between each Telegram API call
    to prevent pool exhaustion under high member counts.
    """
    chat_id = group.telegram_chat_id
    group_id = group.id

    rows = list(
        (
            await session.scalars(
                select(GroupMember).where(
                    GroupMember.group_id == group_id,
                    GroupMember.is_present.is_(True),
                ).order_by(GroupMember.id)
            )
        ).all()
    )

    checked = deleted = present = inaccessible = 0
    for row in rows:
        try:
            member = await _telegram_call(
                lambda uid=row.user_telegram_id: bot.get_chat_member(chat_id, uid)
            )
        except (TelegramBadRequest, TelegramForbiddenError):
            inaccessible += 1
            continue
        checked += 1
        row.last_checked_at = datetime.now(timezone.utc)
        if member.status in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}:
            row.is_present = False
            continue
        row.is_present = True
        present += 1
        user = member.user
        row.is_deleted_account = is_deleted_profile(user)
        if row.is_deleted_account:
            deleted += 1
        await upsert_user(session, user)
    await session.flush()
    return ScanResult(
        checked=checked,
        deleted=deleted,
        present=present,
        inaccessible=inaccessible,
    )


async def remove_deleted_accounts(
    bot: Bot,
    session: AsyncSession,
    group: Group,
) -> CleanupResult:
    """Remove known Telegram "Deleted Account" profiles from a group.

    Only rows that were positively identified as deleted and are still marked
    present are touched. A successful ban removes the account from the chat;
    deleted accounts cannot meaningfully rejoin, so no unban is needed.
    Telegram/API failures are counted and do not abort the whole cleanup.
    """
    rows = list(
        (
            await session.scalars(
                select(GroupMember).where(
                    GroupMember.group_id == group.id,
                    GroupMember.is_present.is_(True),
                    GroupMember.is_deleted_account.is_(True),
                ).order_by(GroupMember.id)
            )
        ).all()
    )
    removed = failed = 0
    for row in rows:
        try:
            await _telegram_call(
                lambda uid=row.user_telegram_id: bot.ban_chat_member(
                    chat_id=group.telegram_chat_id,
                    user_id=uid,
                    revoke_messages=False,
                )
            )
        except (TelegramBadRequest, TelegramForbiddenError):
            failed += 1
            continue
        row.is_present = False
        row.last_checked_at = datetime.now(timezone.utc)
        removed += 1
    await session.flush()
    return CleanupResult(found=len(rows), removed=removed, failed=failed)
