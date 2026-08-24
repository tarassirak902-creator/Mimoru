from __future__ import annotations

from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group, JoinRequestRecord
from app.services.access import is_service_owner
from app.services.join_request_transitions import PROCESSING_APPROVE, PROCESSING_DECLINE, REVIEW_UNCERTAIN


@dataclass(slots=True)
class JoinReviewExecutionResult:
    status: str
    request_status: str | None = None
    error_text: str | None = None


def _reset_review_claim(row: JoinRequestRecord) -> None:
    row.status = "pending"
    row.reviewed_at = None
    row.reviewed_by_telegram_id = None


async def execute_join_review(
    session: AsyncSession,
    bot: Bot,
    *,
    request_id: int,
    approve: bool,
) -> JoinReviewExecutionResult:
    group_id = await session.scalar(
        select(JoinRequestRecord.group_id).where(JoinRequestRecord.id == request_id)
    )
    if group_id is None:
        return JoinReviewExecutionResult("not_found")

    group = await session.scalar(
        select(Group).where(Group.id == group_id).with_for_update()
    )
    row = await session.scalar(
        select(JoinRequestRecord)
        .where(JoinRequestRecord.id == request_id)
        .with_for_update()
    )
    expected = PROCESSING_APPROVE if approve else PROCESSING_DECLINE
    if row is None or row.status != expected:
        return JoinReviewExecutionResult("not_claimed", request_status=row.status if row else None)

    actor_id = row.reviewed_by_telegram_id
    if group is None or not group.is_active:
        row.status = REVIEW_UNCERTAIN
        await session.commit()
        return JoinReviewExecutionResult("inactive", request_status=row.status)

    if actor_id is None or (
        actor_id != group.owner_telegram_id and not is_service_owner(actor_id)
    ):
        _reset_review_claim(row)
        await session.commit()
        return JoinReviewExecutionResult("stale_actor", request_status=row.status)

    try:
        if approve:
            await bot.approve_chat_join_request(group.telegram_chat_id, row.user_telegram_id)
        else:
            await bot.decline_chat_join_request(group.telegram_chat_id, row.user_telegram_id)
    except (TelegramBadRequest, TelegramForbiddenError) as error:
        _reset_review_claim(row)
        await session.commit()
        return JoinReviewExecutionResult(
            "telegram_error",
            request_status=row.status,
            error_text=str(error)[:1000],
        )

    row.status = "approved" if approve else "declined"
    await session.commit()
    return JoinReviewExecutionResult("completed", request_status=row.status)
