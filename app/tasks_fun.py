from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, timezone

import structlog
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy import select

from app.db.fun_models import FunAutoImmunity, FunGroupSettings, GameEvent
from app.db.models import Group, GroupMember
from app.db.session import SessionFactory
from app.handlers.fun_commands import FUN_ACTIONS, _pick_text


MAX_GROUPS_PER_TICK = 8
TICK_SECONDS = 60
AUTO_TICK_ACTION = "auto_tick"
INTERVALS = {
    "15_20": (15, 20),
    "30_40": (30, 40),
    "60": (60, 60),
}


def _display_name(user) -> str:
    if user.username:
        return f"@{user.username}"
    return user.full_name or str(user.id)


def _group_interval(group_id: int, interval_code: str) -> timedelta:
    minimum, maximum = INTERVALS.get(interval_code, INTERVALS["15_20"])
    span = maximum - minimum + 1
    minutes = minimum + ((group_id * 2654435761) % span)
    return timedelta(minutes=minutes)


def _format_action(action: str, target_name: str) -> str:
    return _pick_text(action).format(
        user1="Mimoru",
        user2=target_name,
        chance=random.randint(0, 100),
        loot=random.randint(1, 999),
        sentence=random.randint(1, 60),
    )


async def _pick_target(bot: Bot, group_id: int, telegram_chat_id: int, members: list[GroupMember]):
    candidates = list(members)
    random.shuffle(candidates)
    for member in candidates[:30]:
        try:
            chat_member = await bot.get_chat_member(telegram_chat_id, member.user_telegram_id)
        except (TelegramBadRequest, TelegramForbiddenError):
            continue
        if chat_member.status in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}:
            continue
        user = chat_member.user
        if user.is_bot:
            continue
        return user
    return None


async def _claim_auto_tick(
    bot_id: int,
    group_id: int,
    now: datetime,
) -> datetime | None:
    """Claim one due auto-activity interval while serializing on the group row.

    The scan event is committed before the caller performs any Telegram side effect.
    A concurrent replica blocks on the same group row, then re-reads the new scan and
    observes that the interval is no longer due.
    """
    async with SessionFactory() as session:
        group = await session.scalar(
            select(Group)
            .where(Group.id == group_id, Group.is_active.is_(True))
            .with_for_update()
        )
        if group is None:
            return None

        settings = await session.scalar(
            select(FunGroupSettings).where(FunGroupSettings.group_id == group_id)
        )
        if settings is not None and not settings.auto_enabled:
            return None
        interval_code = settings.interval_code if settings is not None else "15_20"
        last_tick = await session.scalar(
            select(GameEvent.created_at).where(
                GameEvent.group_id == group_id,
                GameEvent.event_type == "system",
                GameEvent.action == AUTO_TICK_ACTION,
            ).order_by(GameEvent.created_at.desc()).limit(1)
        )

        if last_tick is None:
            session.add(GameEvent(
                group_id=group_id,
                event_type="system",
                action=AUTO_TICK_ACTION,
                actor_telegram_id=bot_id,
                target_telegram_id=bot_id,
                actor_name="Mimoru",
                target_name="Mimoru",
                outcome="init",
            ))
            await session.commit()
            return None

        if last_tick + _group_interval(group_id, interval_code) > now:
            return None

        session.add(GameEvent(
            group_id=group_id,
            event_type="system",
            action=AUTO_TICK_ACTION,
            actor_telegram_id=bot_id,
            target_telegram_id=bot_id,
            actor_name="Mimoru",
            target_name="Mimoru",
            outcome="scan",
        ))
        await session.commit()
        return last_tick


async def _run_claimed_auto_activity(
    bot: Bot,
    group_id: int,
    window_start: datetime,
    now: datetime,
) -> None:
    """Run one auto-activity tick for a group.

    Session lifecycle: the Group FOR UPDATE lock is held only during validation
    and the final GameEvent insert. Telegram API calls (get_chat_member,
    send_message) happen between separate short transactions so the pool is
    never held during potentially 30+ sequential Telegram calls.
    """
    log = structlog.get_logger()
    telegram_chat_id = None
    member_ids = []

    # --- Phase 1: Validate under Group FOR UPDATE lock, collect candidates ---
    async with SessionFactory() as session:
        group = await session.scalar(
            select(Group)
            .where(Group.id == group_id, Group.is_active.is_(True))
            .with_for_update()
        )
        if group is None:
            return
        settings = await session.scalar(
            select(FunGroupSettings).where(FunGroupSettings.group_id == group.id)
        )
        if settings is not None and not settings.auto_enabled:
            return

        telegram_chat_id = group.telegram_chat_id
        immune_ids = set((await session.scalars(
            select(FunAutoImmunity.user_telegram_id).where(
                FunAutoImmunity.group_id == group.id,
                FunAutoImmunity.enabled.is_(True),
            )
        )).all())
        member_rows = list((await session.execute(
            select(GroupMember.id, GroupMember.user_telegram_id).where(
                GroupMember.group_id == group.id,
                GroupMember.is_present.is_(True),
                GroupMember.is_deleted_account.is_(False),
                GroupMember.last_seen_at > window_start,
                GroupMember.last_seen_at <= now,
            ).order_by(GroupMember.last_seen_at.desc()).limit(120)
        )).all())

    if not member_rows or telegram_chat_id is None:
        return

    # Filter out immune members (row[1] = user_telegram_id)
    member_ids = [row[0] for row in member_rows if row[1] not in immune_ids]
    if not member_ids:
        return

    # --- Phase 2: Load candidates in one short DB query, then release connection ---
    async with SessionFactory() as session:
        members = list((await session.scalars(
            select(GroupMember).where(GroupMember.id.in_(member_ids))
        )).all())
    if not members:
        return

    # --- Phase 3: Pick target via Telegram API (NO connection held) ---
    target = await _pick_target(bot, group_id, telegram_chat_id, members)
    if target is None:
        return

    # --- Phase 4: Send message (NO connection held) ---
    action = random.choice(tuple(FUN_ACTIONS))
    target_name = _display_name(target)
    try:
        await bot.send_message(telegram_chat_id, _format_action(action, target_name))
    except (TelegramBadRequest, TelegramForbiddenError) as error:
        log.warning("fun_auto_send_failed", group_id=group_id, error=str(error))
        return

    # --- Phase 5: Persist event under Group FOR UPDATE lock ---
    async with SessionFactory() as session:
        group = await session.scalar(
            select(Group)
            .where(Group.id == group_id, Group.is_active.is_(True))
            .with_for_update()
        )
        if group is None:
            return
        session.add(GameEvent(
            group_id=group.id,
            event_type="action",
            action=action,
            actor_telegram_id=bot.id,
            target_telegram_id=target.id,
            actor_name="Mimoru",
            target_name=target_name,
            outcome="auto",
        ))
        await session.commit()


async def run_fun_auto_activity(bot: Bot) -> None:
    now = datetime.now(timezone.utc)
    async with SessionFactory() as session:
        group_ids = list((await session.scalars(
            select(Group.id).where(Group.is_active.is_(True)).order_by(Group.id)
        )).all())

    random.shuffle(group_ids)
    claimed = 0
    for group_id in group_ids:
        window_start = await _claim_auto_tick(bot.id, group_id, now)
        if window_start is None:
            continue
        await _run_claimed_auto_activity(bot, group_id, window_start, now)
        claimed += 1
        if claimed >= MAX_GROUPS_PER_TICK:
            break


async def fun_background_loop(bot: Bot, stop_event: asyncio.Event) -> None:
    log = structlog.get_logger()
    while not stop_event.is_set():
        try:
            await run_fun_auto_activity(bot)
        except Exception:
            log.exception("fun_background_iteration_failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=TICK_SECONDS)
        except TimeoutError:
            continue
