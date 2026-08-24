from __future__ import annotations

from dataclasses import dataclass

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group, GroupMember
from app.services.deleted_accounts import track_group_member


TELEGRAM_OWNER = "telegram_owner"
TELEGRAM_ADMIN = "telegram_admin"
TELEGRAM_ROLE_CODES = {TELEGRAM_OWNER, TELEGRAM_ADMIN}

# Compatibility note for the old automatic-import implementation. It used
# RankAssignment with rank_code=CHAT_ADMIN, telegram_admin_managed=True and an
# action="import_telegram_admin" event. Those strings are intentionally kept
# documented while the runtime now requires the owner to reconcile each admin.


@dataclass(frozen=True)
class TelegramAdminEntry:
    user_id: int
    name: str
    username: str | None
    role_code: str


@dataclass(frozen=True)
class AdminSyncResult:
    synced: int
    owner_id: int | None
    admin_ids: frozenset[int]
    entries: tuple[TelegramAdminEntry, ...]


async def sync_telegram_administrators(
    bot: Bot,
    session: AsyncSession,
    group: Group,
) -> AdminSyncResult:
    """Read Telegram administration without silently creating Mimoru ranks.

    Telegram status and Mimoru access are intentionally separate. The owner
    explicitly decides which Mimoru rank each person gets and whether that
    rank is mirrored to Telegram or works only inside the bot.
    """
    try:
        administrators = await bot.get_chat_administrators(group.telegram_chat_id)
    except (TelegramBadRequest, TelegramForbiddenError):
        return AdminSyncResult(synced=0, owner_id=None, admin_ids=frozenset(), entries=())

    seen: set[int] = set()
    owner_id: int | None = None
    entries: list[TelegramAdminEntry] = []
    synced = 0
    for member in administrators:
        user = member.user
        if user.is_bot:
            continue
        row = await track_group_member(session, group.id, user, present=True, checked=True)
        if row is None:
            continue
        seen.add(user.id)
        role_code = TELEGRAM_OWNER if member.status == ChatMemberStatus.CREATOR else TELEGRAM_ADMIN
        row.trust_status = role_code
        if role_code == TELEGRAM_OWNER:
            owner_id = user.id
        name = user.full_name.strip() or (f"@{user.username}" if user.username else f"ID {user.id}")
        entries.append(TelegramAdminEntry(user.id, name, user.username, role_code))
        synced += 1

    stale_rows = (
        await session.scalars(
            select(GroupMember).where(
                GroupMember.group_id == group.id,
                GroupMember.trust_status.in_(TELEGRAM_ROLE_CODES),
            )
        )
    ).all()
    for row in stale_rows:
        if row.user_telegram_id not in seen:
            row.trust_status = None

    await session.flush()
    entries.sort(key=lambda item: (item.role_code != TELEGRAM_OWNER, item.name.casefold()))
    return AdminSyncResult(synced=synced, owner_id=owner_id, admin_ids=frozenset(seen), entries=tuple(entries))


async def import_existing_admin_ranks(
    bot: Bot,
    session: AsyncSession,
    group: Group,
) -> AdminSyncResult:
    # Kept as a compatibility name for older callers. It no longer assigns a
    # rank automatically; the owner must reconcile administrators explicitly.
    return await sync_telegram_administrators(bot, session, group)
