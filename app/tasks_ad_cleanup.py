from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import NamedTuple

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy import select, update

from app.db.models import AdOrder, AdPlacement, Group
from app.db.session import SessionFactory


CLEANUP_PENDING = "cleanup_pending"


class _CleanupClaim(NamedTuple):
    order_id: int
    group_id: int
    published_message_id: int | None


def _message_definitely_absent(error: TelegramBadRequest) -> bool:
    """Recognize only Telegram's explicit already-absent delete result.

    Other BadRequest variants can mean permissions, age limits, invalid chat state,
    or another retryable condition and must not silently complete a commercial order.
    """
    text = str(error).casefold()
    return "message to delete not found" in text


async def _claim_due_order(order_id: int, now: datetime) -> _CleanupClaim | None:
    """Persist cleanup ownership before the Telegram delete side effect."""
    async with SessionFactory() as session:
        order = await session.scalar(
            select(AdOrder).where(AdOrder.id == order_id).with_for_update()
        )
        if order is None:
            return None
        placement = await session.get(AdPlacement, order.placement_id)
        if placement is None:
            if order.status != CLEANUP_PENDING:
                order.status = "completed"
                order.completed_at = now
                await session.commit()
            return None
        if order.status == CLEANUP_PENDING:
            return _CleanupClaim(order.id, placement.group_id, order.published_message_id)
        if order.status != "published" or order.published_at is None:
            return None
        expires_at = order.published_at + timedelta(hours=max(1, placement.duration_hours))
        if expires_at > now:
            return None
        order.status = CLEANUP_PENDING
        claim = _CleanupClaim(order.id, placement.group_id, order.published_message_id)
        await session.commit()
        return claim


async def _finish_cleanup(order_id: int, now: datetime) -> None:
    async with SessionFactory() as session:
        await session.execute(
            update(AdOrder)
            .where(
                AdOrder.id == order_id,
                AdOrder.status == CLEANUP_PENDING,
            )
            .values(status="completed", completed_at=now)
        )
        await session.commit()


async def complete_ad_orders(bot: Bot) -> None:
    """Remove expired ads and complete orders only after confirmed cleanup.

    `cleanup_pending` is durable across restarts. A repeated delete after a crash is
    safe: explicit Telegram "message to delete not found" proves the original
    message is already absent and can therefore finalize the order.
    """
    log = structlog.get_logger()
    now = datetime.now(timezone.utc)
    async with SessionFactory() as session:
        candidate_ids = list((await session.scalars(
            select(AdOrder.id)
            .where(AdOrder.status.in_(["published", CLEANUP_PENDING]))
            .order_by(AdOrder.id)
            .limit(100)
        )).all())

    for order_id in candidate_ids:
        claim = await _claim_due_order(order_id, now)
        if claim is None:
            continue

        async with SessionFactory() as session:
            group = await session.get(Group, claim.group_id)

        if group is None or claim.published_message_id is None:
            await _finish_cleanup(claim.order_id, now)
            continue

        try:
            await bot.delete_message(group.telegram_chat_id, claim.published_message_id)
        except TelegramForbiddenError as error:
            log.warning(
                "ad_expiry_delete_retryable",
                order_id=claim.order_id,
                group_id=group.id,
                error=str(error),
            )
            continue
        except TelegramBadRequest as error:
            if not _message_definitely_absent(error):
                log.warning(
                    "ad_expiry_delete_retryable",
                    order_id=claim.order_id,
                    group_id=group.id,
                    error=str(error),
                )
                continue
            log.info(
                "ad_expiry_message_already_absent",
                order_id=claim.order_id,
                group_id=group.id,
            )

        await _finish_cleanup(claim.order_id, now)
