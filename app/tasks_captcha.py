from __future__ import annotations

from datetime import datetime, timezone

import structlog
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError
from redis.asyncio import Redis
from sqlalchemy import select

from app.db.models import Group, Punishment
from app.db.session import SessionFactory
from app.services.captcha_state import (
    BAN_INFLIGHT,
    PENDING_BAN,
    PENDING_UNBAN,
    PROCESSING_TTL_SECONDS,
    VERIFIED,
    claim_expired_captcha,
    delete_captcha_state,
    refresh_captcha_state_ttl,
)
from app.services.captcha_verification import finalize_verified_captcha


def _captcha_parts(key: str) -> tuple[int, int] | None:
    try:
        _, raw_chat_id, raw_user_id = key.split(":", 2)
        return int(raw_chat_id), int(raw_user_id)
    except (TypeError, ValueError):
        return None


async def _member_is_banned(bot: Bot, chat_id: int, user_id: int) -> bool | None:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
    except (TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError):
        return None
    return member.status == ChatMemberStatus.KICKED


async def _run_verified(bot: Bot, redis: Redis, key: str, chat_id: int, user_id: int) -> None:
    """Finish verification under the same Group permission boundary as moderation."""
    async with SessionFactory() as session:
        await finalize_verified_captcha(
            bot,
            redis,
            session,
            key=key,
            chat_id=chat_id,
            user_id=user_id,
        )
        # Release the Group row lock even when Telegram unrestrict must be retried.
        await session.commit()


async def _run_pending_ban(bot: Bot, redis: Redis, key: str, chat_id: int, user_id: int) -> None:
    await redis.set(key, BAN_INFLIGHT, ex=PROCESSING_TTL_SECONDS)
    try:
        await bot.ban_chat_member(chat_id, user_id)
    except (TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError) as error:
        structlog.get_logger().warning(
            "captcha_expiry_ban_failed",
            chat_id=chat_id,
            user_id=user_id,
            error=str(error),
        )
        await redis.set(key, PENDING_BAN, ex=PROCESSING_TTL_SECONDS)
        return
    await redis.set(key, PENDING_UNBAN, ex=PROCESSING_TTL_SECONDS)


async def _run_pending_unban(bot: Bot, redis: Redis, key: str, chat_id: int, user_id: int) -> None:
    """Undo only the CAPTCHA kick, never a concurrent moderation ban."""
    async with SessionFactory() as session:
        group = await session.scalar(
            select(Group)
            .where(Group.telegram_chat_id == chat_id)
            .with_for_update()
        )

        # Another worker or callback may have moved/cleared this recovery state
        # while we were waiting for the Group serialization boundary.
        if await redis.get(key) != PENDING_UNBAN:
            await session.commit()
            return

        if group is not None:
            active_ban = await session.scalar(
                select(Punishment.id).where(
                    Punishment.group_id == group.id,
                    Punishment.user_telegram_id == user_id,
                    Punishment.kind == "ban",
                    Punishment.active.is_(True),
                ).limit(1)
            )
            if active_ban is not None:
                # CAPTCHA expiry is complete, but the independent moderation ban
                # must remain authoritative in Telegram.
                await delete_captcha_state(redis, key, PENDING_UNBAN)
                await session.commit()
                return

        banned = await _member_is_banned(bot, chat_id, user_id)
        if banned is False:
            await delete_captcha_state(redis, key, PENDING_UNBAN)
            await session.commit()
            return
        if banned is None:
            await refresh_captcha_state_ttl(redis, key, PENDING_UNBAN)
            await session.commit()
            return
        try:
            await bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
        except (TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError) as error:
            structlog.get_logger().warning(
                "captcha_expiry_unban_failed",
                chat_id=chat_id,
                user_id=user_id,
                error=str(error),
            )
            await refresh_captcha_state_ttl(redis, key, PENDING_UNBAN)
            await session.commit()
            return
        await delete_captcha_state(redis, key, PENDING_UNBAN)
        await session.commit()


async def expire_captcha_sessions(bot: Bot, redis: Redis) -> None:
    """Expire CAPTCHA sessions while preserving an atomic verification/expiry winner."""
    now_ts = int(datetime.now(timezone.utc).timestamp())
    async for key in redis.scan_iter(match="captcha:*", count=200):
        raw_value = await redis.get(key)
        if not raw_value:
            continue
        parsed = _captcha_parts(key)
        if parsed is None:
            await redis.delete(key)
            continue
        chat_id, user_id = parsed

        state = raw_value
        if raw_value.lstrip("-").isdigit():
            if int(raw_value) > now_ts:
                continue
            claim_result = await claim_expired_captcha(redis, key, raw_value, now_ts)
            if claim_result != 1:
                continue
            state = PENDING_BAN

        if state == VERIFIED:
            await _run_verified(bot, redis, key, chat_id, user_id)
            continue

        if state == BAN_INFLIGHT:
            banned = await _member_is_banned(bot, chat_id, user_id)
            if banned is None:
                await refresh_captcha_state_ttl(redis, key, BAN_INFLIGHT)
                continue
            state = PENDING_UNBAN if banned else PENDING_BAN
            await redis.set(key, state, ex=PROCESSING_TTL_SECONDS)

        if state == PENDING_BAN:
            await _run_pending_ban(bot, redis, key, chat_id, user_id)
            state = await redis.get(key) or ""

        if state == PENDING_UNBAN:
            await _run_pending_unban(bot, redis, key, chat_id, user_id)
            continue

        if state not in {PENDING_BAN, BAN_INFLIGHT, PENDING_UNBAN, VERIFIED}:
            structlog.get_logger().warning(
                "captcha_expiry_unknown_state",
                key=key,
                state=state,
            )
