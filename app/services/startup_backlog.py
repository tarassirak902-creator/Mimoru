from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message, Update
from redis.asyncio import Redis


CRITICAL_MODERATION_TTL_SECONDS = 300
RECOVERY_NOTICE_USERS_KEY = "mimoru:recovery:notice_users"
RECOVERY_CRITICAL_CLAIM_PREFIX = "mimoru:recovery:critical_claim:"
_RECOVERY_NOTICE_TEXT = (
    "🟢 Mimoru снова работает.\n\n"
    "Некоторые действия, отправленные во время недоступности бота, не были выполнены. "
    "Пожалуйста, повторите нужное действие."
)
_CRITICAL_COMMANDS = {"бан", "мут", "пред"}
_GROUP_TYPES = {"group", "supergroup"}


def _update_user_id(update: Update) -> int | None:
    for event in (
        update.message,
        update.edited_message,
        update.callback_query,
        update.pre_checkout_query,
        update.chat_join_request,
        update.chat_member,
        update.my_chat_member,
    ):
        user = getattr(event, "from_user", None) if event is not None else None
        if user is not None:
            return user.id
    return None


def _critical_group_message(update: Update, *, now: datetime) -> bool:
    message = update.message
    if not isinstance(message, Message) or message.chat.type not in _GROUP_TYPES:
        return False
    text = (message.text or "").strip()
    if not text:
        return False
    first_line = text.splitlines()[0].strip().casefold()
    command = first_line.split(maxsplit=1)[0] if first_line else ""
    if command not in _CRITICAL_COMMANDS:
        return False
    message_time = message.date
    if message_time.tzinfo is None:
        message_time = message_time.replace(tzinfo=timezone.utc)
    age = (now - message_time.astimezone(timezone.utc)).total_seconds()
    return 0 <= age <= CRITICAL_MODERATION_TTL_SECONDS


async def _queue_recovery_notice(redis: Redis, update: Update) -> None:
    user_id = _update_user_id(update)
    if user_id is not None:
        await redis.sadd(RECOVERY_NOTICE_USERS_KEY, user_id)


async def _claim_critical(redis: Redis, update_id: int) -> bool:
    key = f"{RECOVERY_CRITICAL_CLAIM_PREFIX}{update_id}"
    return bool(await redis.set(key, "1", ex=86400, nx=True))


async def drain_startup_backlog(
    bot: Bot,
    dispatcher: Dispatcher,
    redis: Redis,
    *,
    allowed_updates: list[str] | None = None,
) -> dict[str, int]:
    """Drain queued Telegram updates before normal polling.

    Old UI/navigation updates are acknowledged and discarded. Only fresh group
    moderation text commands (бан/мут/пред, <=5 minutes old) are fed through the
    normal Dispatcher, with an update-id claim to prevent duplicate replay.
    """
    log = structlog.get_logger()
    offset: int | None = None
    recovered: list[Update] = []
    dropped = 0
    batches = 0

    while True:
        updates = await bot.get_updates(
            offset=offset,
            limit=100,
            timeout=0,
            allowed_updates=allowed_updates,
        )
        if not updates:
            break
        batches += 1
        now = datetime.now(timezone.utc)
        for update in updates:
            offset = update.update_id + 1
            if _critical_group_message(update, now=now):
                recovered.append(update)
            else:
                dropped += 1
                await _queue_recovery_notice(redis, update)
        if len(updates) < 100:
            # One explicit offset call below confirms the final page too.
            break

    if offset is not None:
        await bot.get_updates(
            offset=offset,
            limit=1,
            timeout=0,
            allowed_updates=allowed_updates,
        )

    executed = 0
    skipped_duplicate = 0
    for update in recovered:
        if not await _claim_critical(redis, update.update_id):
            skipped_duplicate += 1
            continue
        await dispatcher.feed_update(bot, update)
        executed += 1

    if dropped or recovered:
        log.info(
            "startup_backlog_drained",
            batches=batches,
            dropped=dropped,
            recovered=executed,
            duplicate_critical_skipped=skipped_duplicate,
        )
    return {
        "dropped": dropped,
        "recovered": executed,
        "duplicate_critical_skipped": skipped_duplicate,
    }


async def send_recovery_notices(bot: Bot, redis: Redis, stop_event: asyncio.Event) -> None:
    """Send at most one recovery notice per affected user without a request burst."""
    log = structlog.get_logger()
    while not stop_event.is_set():
        raw_user_id = await redis.spop(RECOVERY_NOTICE_USERS_KEY)
        if raw_user_id is None:
            return
        try:
            user_id = int(raw_user_id)
        except (TypeError, ValueError):
            continue
        try:
            await bot.send_message(user_id, _RECOVERY_NOTICE_TEXT)
        except (TelegramForbiddenError, TelegramBadRequest):
            pass
        except Exception:
            # Preserve the notice for a later retry if Telegram/network failed.
            await redis.sadd(RECOVERY_NOTICE_USERS_KEY, user_id)
            log.exception("recovery_notice_failed", user_id=user_id)
            return
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=0.2)
        except TimeoutError:
            pass
