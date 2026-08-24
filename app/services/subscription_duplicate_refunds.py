from __future__ import annotations

from datetime import datetime, timezone

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.payment_refund_models import SubscriptionDuplicateRefund
from app.db.session import SessionFactory


log = structlog.get_logger()


def _already_refunded(error: TelegramBadRequest) -> bool:
    text = str(error).casefold()
    return "refund" in text and "already" in text


async def ensure_subscription_duplicate_refund(
    session: AsyncSession,
    *,
    payment_id: int,
    buyer_telegram_id: int,
    charge_id: str,
) -> int:
    existing = await session.scalar(
        select(SubscriptionDuplicateRefund).where(
            SubscriptionDuplicateRefund.telegram_payment_charge_id == charge_id
        )
    )
    if existing is not None:
        return existing.id

    row = SubscriptionDuplicateRefund(
        payment_id=payment_id,
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
            select(SubscriptionDuplicateRefund.id).where(
                SubscriptionDuplicateRefund.telegram_payment_charge_id == charge_id
            )
        )
        if existing_id is None:
            raise
        return existing_id


async def attempt_subscription_duplicate_refund(
    bot: Bot,
    session: AsyncSession,
    refund_id: int,
) -> bool:
    row = await session.scalar(
        select(SubscriptionDuplicateRefund)
        .where(SubscriptionDuplicateRefund.id == refund_id)
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
                "subscription_duplicate_charge_refund_failed",
                refund_id=row.id,
                payment_id=row.payment_id,
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


async def record_and_attempt_subscription_duplicate_refund(
    bot: Bot,
    session: AsyncSession,
    *,
    payment_id: int,
    buyer_telegram_id: int,
    charge_id: str,
) -> bool:
    refund_id = await ensure_subscription_duplicate_refund(
        session,
        payment_id=payment_id,
        buyer_telegram_id=buyer_telegram_id,
        charge_id=charge_id,
    )
    return await attempt_subscription_duplicate_refund(bot, session, refund_id)


async def recover_pending_subscription_duplicate_refunds(bot: Bot, *, limit: int = 50) -> None:
    async with SessionFactory() as session:
        refund_ids = list((await session.scalars(
            select(SubscriptionDuplicateRefund.id)
            .where(SubscriptionDuplicateRefund.status == "pending")
            .order_by(SubscriptionDuplicateRefund.created_at, SubscriptionDuplicateRefund.id)
            .limit(limit)
        )).all())

    for refund_id in refund_ids:
        async with SessionFactory() as session:
            await attempt_subscription_duplicate_refund(bot, session, refund_id)
