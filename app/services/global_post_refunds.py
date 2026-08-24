from __future__ import annotations

from datetime import datetime, timezone

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.payment_refund_models import GlobalPostDuplicateRefund
from app.db.session import SessionFactory


log = structlog.get_logger()


def _already_refunded(error: TelegramBadRequest) -> bool:
    text = str(error).casefold()
    return "refund" in text and "already" in text


async def ensure_duplicate_refund(
    session: AsyncSession,
    *,
    request_id: int,
    buyer_telegram_id: int,
    charge_id: str,
) -> int:
    """Durably record a refund obligation before any Telegram side effect."""
    existing = await session.scalar(
        select(GlobalPostDuplicateRefund).where(
            GlobalPostDuplicateRefund.telegram_payment_charge_id == charge_id
        )
    )
    if existing is not None:
        return existing.id

    row = GlobalPostDuplicateRefund(
        request_id=request_id,
        buyer_telegram_id=buyer_telegram_id,
        telegram_payment_charge_id=charge_id,
        status="pending",
    )
    session.add(row)
    try:
        await session.commit()
        return row.id
    except IntegrityError:
        await session.rollback()
        existing_id = await session.scalar(
            select(GlobalPostDuplicateRefund.id).where(
                GlobalPostDuplicateRefund.telegram_payment_charge_id == charge_id
            )
        )
        if existing_id is None:
            raise
        return existing_id


async def attempt_duplicate_refund(
    bot: Bot,
    session: AsyncSession,
    refund_id: int,
) -> bool:
    """Attempt one refund while serializing competing live/recovery workers."""
    row = await session.scalar(
        select(GlobalPostDuplicateRefund)
        .where(GlobalPostDuplicateRefund.id == refund_id)
        .with_for_update()
    )
    if row is None:
        return False
    if row.status == "refunded":
        return True

    row.attempts += 1
    try:
        await bot.refund_star_payment(
            user_id=row.buyer_telegram_id,
            telegram_payment_charge_id=row.telegram_payment_charge_id,
        )
    except TelegramBadRequest as error:
        if not _already_refunded(error):
            row.last_error = str(error)[:2000]
            await session.commit()
            log.warning(
                "global_post_duplicate_charge_refund_failed",
                refund_id=row.id,
                request_id=row.request_id,
                user_id=row.buyer_telegram_id,
                duplicate_charge_id=row.telegram_payment_charge_id,
                attempts=row.attempts,
                error=str(error),
            )
            return False

    row.status = "refunded"
    row.last_error = None
    row.refunded_at = datetime.now(timezone.utc)
    await session.commit()
    return True


async def record_and_attempt_duplicate_refund(
    bot: Bot,
    session: AsyncSession,
    *,
    request_id: int,
    buyer_telegram_id: int,
    charge_id: str,
) -> bool:
    refund_id = await ensure_duplicate_refund(
        session,
        request_id=request_id,
        buyer_telegram_id=buyer_telegram_id,
        charge_id=charge_id,
    )
    return await attempt_duplicate_refund(bot, session, refund_id)


async def recover_pending_duplicate_refunds(bot: Bot, *, limit: int = 50) -> None:
    """Retry durable pending refunds without replaying any advertising delivery."""
    async with SessionFactory() as session:
        refund_ids = list((await session.scalars(
            select(GlobalPostDuplicateRefund.id)
            .where(GlobalPostDuplicateRefund.status == "pending")
            .order_by(GlobalPostDuplicateRefund.created_at, GlobalPostDuplicateRefund.id)
            .limit(limit)
        )).all())

    for refund_id in refund_ids:
        async with SessionFactory() as session:
            await attempt_duplicate_refund(bot, session, refund_id)
