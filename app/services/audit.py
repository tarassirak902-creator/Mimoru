from datetime import datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy import select

from app.db.models import Group, ModerationLog
from app.db.session import SessionFactory
from app.services.audit_format import render_log


MAX_DELIVERY_ATTEMPTS = 5
UNCERTAIN_DELIVERY_ERROR = (
    "Предыдущая доставка журнала была прервана после фиксации отправки. "
    "Состояние Telegram неизвестно; автоматический повтор отключён во избежание дубля."
)


async def _mark_audit_delivery_uncertain(row_id: int) -> int | None:
    """Durably enter the ambiguous Telegram-send window for one audit row."""
    async with SessionFactory() as session:
        row = await session.scalar(
            select(ModerationLog)
            .where(
                ModerationLog.id == row_id,
                ModerationLog.delivered_at.is_(None),
                ModerationLog.delivery_attempts < MAX_DELIVERY_ATTEMPTS,
            )
            .with_for_update()
        )
        if row is None:
            return None

        attempts_before_claim = row.delivery_attempts
        row.delivery_attempts = MAX_DELIVERY_ATTEMPTS
        row.delivery_error = UNCERTAIN_DELIVERY_ERROR
        await session.commit()
        return attempts_before_claim


async def _finalize_audit_delivery(row_id: int) -> None:
    async with SessionFactory() as session:
        row = await session.scalar(
            select(ModerationLog).where(ModerationLog.id == row_id).with_for_update()
        )
        if (
            row is None
            or row.delivered_at is not None
            or row.delivery_error != UNCERTAIN_DELIVERY_ERROR
        ):
            return
        row.delivered_at = datetime.now(timezone.utc)
        row.delivery_error = None
        await session.commit()


async def _release_definite_audit_failure(
    row_id: int,
    *,
    attempts_before_claim: int,
    error: Exception,
) -> None:
    """Return only a definitely-unsent Telegram rejection to the retry budget."""
    async with SessionFactory() as session:
        row = await session.scalar(
            select(ModerationLog).where(ModerationLog.id == row_id).with_for_update()
        )
        if (
            row is None
            or row.delivered_at is not None
            or row.delivery_error != UNCERTAIN_DELIVERY_ERROR
        ):
            return
        row.delivery_attempts = min(attempts_before_claim + 1, MAX_DELIVERY_ATTEMPTS)
        row.delivery_error = str(error)[:1000]
        await session.commit()


async def _finish_without_destination(
    session,
    row_id: int,
    *,
    error_text: str,
) -> None:
    """Terminally consume one row when no current audit destination can receive it."""
    row = await session.scalar(
        select(ModerationLog)
        .where(
            ModerationLog.id == row_id,
            ModerationLog.delivered_at.is_(None),
            ModerationLog.delivery_attempts < MAX_DELIVERY_ATTEMPTS,
        )
        .with_for_update()
    )
    if row is None:
        return
    row.delivered_at = datetime.now(timezone.utc)
    row.delivery_error = error_text
    await session.commit()


async def deliver_pending_logs(bot: Bot, limit: int = 100) -> None:
    async with SessionFactory() as session:
        candidates = list((await session.execute(
            select(ModerationLog.id, ModerationLog.group_id)
            .where(
                ModerationLog.delivered_at.is_(None),
                ModerationLog.delivery_attempts < MAX_DELIVERY_ATTEMPTS,
            )
            .order_by(ModerationLog.id)
            .limit(limit)
        )).all())

    for row_id, group_id in candidates:
        # Group is the shared serialization boundary for ownership transfer and
        # audit-destination mutation. Hold it through the Telegram send and durable
        # finalization so an `audit off`/destination change that commits first wins.
        async with SessionFactory() as gate_session:
            group = await gate_session.scalar(
                select(Group).where(Group.id == group_id).with_for_update()
            )
            if group is None:
                await _finish_without_destination(
                    gate_session,
                    row_id,
                    error_text="Группа журнала недоступна",
                )
                continue

            row = await gate_session.scalar(
                select(ModerationLog).where(
                    ModerationLog.id == row_id,
                    ModerationLog.group_id == group_id,
                    ModerationLog.delivered_at.is_(None),
                    ModerationLog.delivery_attempts < MAX_DELIVERY_ATTEMPTS,
                )
            )
            if row is None:
                await gate_session.commit()
                continue

            if group.settings.audit_chat_id is None:
                await _finish_without_destination(
                    gate_session,
                    row_id,
                    error_text="Журнал доставки не настроен",
                )
                continue

            # Render before the durable uncertain marker. A local formatting failure
            # is definitely pre-send and must not quarantine the event.
            text = render_log(group, row)
            chat_id = group.settings.audit_chat_id
            topic_id = group.settings.audit_topic_id

            # Mark the ambiguous window in a separate short transaction while this
            # session retains the Group lock. Do not lock the ModerationLog row in the
            # gate session before this point, otherwise the marker transaction would
            # deadlock waiting for our own row lock.
            attempts_before_claim = await _mark_audit_delivery_uncertain(row_id)
            if attempts_before_claim is None:
                await gate_session.commit()
                continue

            try:
                await bot.send_message(
                    chat_id,
                    text,
                    message_thread_id=topic_id,
                )
            except (TelegramBadRequest, TelegramForbiddenError) as error:
                # Explicit Telegram rejections are definitely unsent and may safely
                # re-enter the bounded retry budget.
                await _release_definite_audit_failure(
                    row_id,
                    attempts_before_claim=attempts_before_claim,
                    error=error,
                )
                await gate_session.commit()
                continue

            # Transport/cancellation/process failures intentionally escape without a
            # catch-all. The uncertain marker survives and the Group transaction is
            # rolled back on context exit, preventing blind resend of a possibly
            # accepted Telegram message.
            await _finalize_audit_delivery(row_id)
            await gate_session.commit()
