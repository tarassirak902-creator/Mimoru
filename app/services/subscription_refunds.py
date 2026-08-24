from __future__ import annotations

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Payment
from app.db.session import SessionFactory


log = structlog.get_logger()


def _already_refunded(error: TelegramBadRequest) -> bool:
    text = str(error).casefold()
    return "refund" in text and "already" in text


async def retry_pending_subscription_refund(
    bot: Bot,
    session: AsyncSession,
    payment_id: int,
) -> bool:
    """Retry one durable stale-subscription refund obligation idempotently."""
    payment = await session.scalar(
        select(Payment).where(Payment.id == payment_id).with_for_update()
    )
    if payment is None:
        return False
    if payment.status == "refunded":
        return True
    if payment.status != "refund_pending":
        return False
    charge_id = payment.provider_payment_id
    if not charge_id:
        log.error(
            "subscription_refund_missing_charge_id",
            payment_id=payment.id,
            user_id=payment.user_telegram_id,
        )
        return False

    try:
        await bot.refund_star_payment(
            user_id=payment.user_telegram_id,
            telegram_payment_charge_id=charge_id,
        )
    except TelegramBadRequest as error:
        if not _already_refunded(error):
            log.warning(
                "subscription_refund_recovery_failed",
                payment_id=payment.id,
                user_id=payment.user_telegram_id,
                charge_id=charge_id,
                error=str(error),
            )
            return False

    payment.status = "refunded"
    await session.commit()
    return True


async def recover_pending_subscription_refunds(bot: Bot, *, limit: int = 20) -> None:
    """Retry a bounded batch of durable subscription refunds."""
    async with SessionFactory() as session:
        payment_ids = list((await session.scalars(
            select(Payment.id)
            .where(Payment.status == "refund_pending")
            .order_by(Payment.paid_at.asc().nullsfirst(), Payment.id.asc())
            .limit(limit)
        )).all())

    for payment_id in payment_ids:
        async with SessionFactory() as session:
            await retry_pending_subscription_refund(bot, session, payment_id)
