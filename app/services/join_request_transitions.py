from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.invite_operation_models import InviteOperation
from app.db.models import Group, InviteCampaign, JoinRequestRecord
from app.db.session import SessionFactory

PROCESSING_APPROVE = "processing_approve"
PROCESSING_DECLINE = "processing_decline"
REVIEW_UNCERTAIN = "review_uncertain"
CREATE_IN_PROGRESS = "creating"
CREATE_UNCERTAIN = "creation_uncertain"
REVOKE_IN_PROGRESS = "revoking"
REVOKE_UNCERTAIN = "revocation_uncertain"
JOIN_REVIEW_CLAIM_STALE_AFTER = timedelta(minutes=5)
INVITE_OPERATION_STALE_AFTER = timedelta(minutes=5)


async def claim_join_review(
    session: AsyncSession,
    *,
    request_id: int,
    group_id: int,
    actor_id: int,
    approve: bool,
) -> JoinRequestRecord | None:
    row = await session.scalar(
        select(JoinRequestRecord)
        .where(
            JoinRequestRecord.id == request_id,
            JoinRequestRecord.group_id == group_id,
            JoinRequestRecord.status == "pending",
        )
        .with_for_update()
    )
    if row is None:
        return None
    row.status = PROCESSING_APPROVE if approve else PROCESSING_DECLINE
    row.reviewed_at = datetime.now(timezone.utc)
    row.reviewed_by_telegram_id = actor_id
    await session.commit()
    return row


async def finalize_join_review(
    session: AsyncSession,
    request_id: int,
    *,
    approve: bool,
) -> JoinRequestRecord | None:
    expected = PROCESSING_APPROVE if approve else PROCESSING_DECLINE
    row = await session.scalar(
        select(JoinRequestRecord)
        .where(JoinRequestRecord.id == request_id)
        .with_for_update()
    )
    if row is None or row.status != expected:
        return None
    row.status = "approved" if approve else "declined"
    await session.commit()
    return row


async def release_failed_join_review(
    session: AsyncSession,
    request_id: int,
    *,
    approve: bool,
) -> None:
    expected = PROCESSING_APPROVE if approve else PROCESSING_DECLINE
    row = await session.scalar(
        select(JoinRequestRecord)
        .where(JoinRequestRecord.id == request_id)
        .with_for_update()
    )
    if row is not None and row.status == expected:
        row.status = "pending"
        row.reviewed_at = None
        row.reviewed_by_telegram_id = None
        await session.commit()


def _join_review_claim_is_stale(row: JoinRequestRecord, now: datetime) -> bool:
    return row.reviewed_at is None or row.reviewed_at <= now - JOIN_REVIEW_CLAIM_STALE_AFTER


async def recover_join_request_reviews(bot: Bot) -> None:
    """Reconcile only stale join-review claims, never a fresh live execution claim."""
    log = structlog.get_logger()
    cutoff = datetime.now(timezone.utc) - JOIN_REVIEW_CLAIM_STALE_AFTER
    async with SessionFactory() as session:
        ids = list((await session.scalars(
            select(JoinRequestRecord.id).where(
                JoinRequestRecord.status.in_([PROCESSING_APPROVE, PROCESSING_DECLINE]),
                or_(
                    JoinRequestRecord.reviewed_at.is_(None),
                    JoinRequestRecord.reviewed_at <= cutoff,
                ),
            )
        )).all())

    for request_id in ids:
        async with SessionFactory() as session:
            group_id = await session.scalar(
                select(JoinRequestRecord.group_id).where(JoinRequestRecord.id == request_id)
            )
            if group_id is None:
                continue
            group = await session.scalar(
                select(Group).where(Group.id == group_id).with_for_update()
            )
            row = await session.scalar(
                select(JoinRequestRecord)
                .where(JoinRequestRecord.id == request_id)
                .with_for_update()
            )
            if row is None or row.status not in {PROCESSING_APPROVE, PROCESSING_DECLINE}:
                continue
            if not _join_review_claim_is_stale(row, datetime.now(timezone.utc)):
                continue
            if group is None or not group.is_active:
                row.status = REVIEW_UNCERTAIN
                await session.commit()
                continue
            try:
                member = await bot.get_chat_member(group.telegram_chat_id, row.user_telegram_id)
            except (TelegramBadRequest, TelegramForbiddenError) as error:
                log.warning(
                    "join_review_recovery_read_failed",
                    request_id=row.id,
                    group_id=group.id,
                    error=str(error),
                )
                continue

            if row.status == PROCESSING_APPROVE and member.status in {
                ChatMemberStatus.CREATOR,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.RESTRICTED,
            }:
                row.status = "approved"
            else:
                # Telegram exposes no authoritative historical state for a consumed
                # join request. A declined request and a request never acted on can
                # both look like LEFT, so do not retry or invent a terminal result.
                row.status = REVIEW_UNCERTAIN
            await session.commit()


async def begin_invite_creation(
    session: AsyncSession,
    *,
    group: Group,
    actor_id: int,
    name: str,
    creates_join_request: bool,
) -> InviteOperation | None:
    await session.scalar(select(Group.id).where(Group.id == group.id).with_for_update())
    existing_campaign = await session.scalar(
        select(InviteCampaign.id).where(
            InviteCampaign.group_id == group.id,
            InviteCampaign.name == name,
        )
    )
    existing_operation = await session.scalar(
        select(InviteOperation.id).where(
            InviteOperation.group_id == group.id,
            InviteOperation.operation == "create",
            InviteOperation.name == name,
            InviteOperation.status.in_([CREATE_IN_PROGRESS, CREATE_UNCERTAIN]),
        )
    )
    if existing_campaign is not None or existing_operation is not None:
        return None
    operation = InviteOperation(
        group_id=group.id,
        operation="create",
        status=CREATE_IN_PROGRESS,
        name=name,
        creates_join_request=creates_join_request,
        actor_telegram_id=actor_id,
    )
    session.add(operation)
    await session.commit()
    return operation


async def finalize_invite_creation(
    session: AsyncSession,
    *,
    operation_id: int,
    invite_link: str,
) -> InviteCampaign | None:
    operation = await session.scalar(
        select(InviteOperation)
        .where(InviteOperation.id == operation_id)
        .with_for_update()
    )
    if operation is None or operation.status != CREATE_IN_PROGRESS or operation.name is None:
        return None
    campaign = InviteCampaign(
        group_id=operation.group_id,
        name=operation.name,
        invite_link=invite_link,
        creates_join_request=bool(operation.creates_join_request),
        created_by_telegram_id=operation.actor_telegram_id,
    )
    session.add(campaign)
    await session.flush()
    operation.campaign_id = campaign.id
    operation.invite_link = invite_link
    operation.status = "completed"
    await session.commit()
    return campaign


async def mark_invite_creation_compensation(
    session: AsyncSession,
    operation_id: int,
    *,
    invite_link: str,
    compensated: bool,
    error_text: str | None = None,
) -> None:
    operation = await session.get(InviteOperation, operation_id)
    if operation is None:
        return
    operation.invite_link = invite_link
    operation.status = "compensated" if compensated else CREATE_UNCERTAIN
    operation.error_text = error_text
    await session.commit()


async def begin_invite_revocation(
    session: AsyncSession,
    *,
    campaign: InviteCampaign,
    actor_id: int,
) -> InviteOperation | None:
    locked = await session.scalar(
        select(InviteCampaign)
        .where(InviteCampaign.id == campaign.id)
        .with_for_update()
    )
    if locked is None or not locked.active:
        return None
    existing = await session.scalar(
        select(InviteOperation.id).where(
            InviteOperation.campaign_id == campaign.id,
            InviteOperation.operation == "revoke",
            InviteOperation.status.in_([REVOKE_IN_PROGRESS, REVOKE_UNCERTAIN]),
        )
    )
    if existing is not None:
        return None
    operation = InviteOperation(
        group_id=campaign.group_id,
        campaign_id=campaign.id,
        operation="revoke",
        status=REVOKE_IN_PROGRESS,
        name=campaign.name,
        invite_link=campaign.invite_link,
        creates_join_request=campaign.creates_join_request,
        actor_telegram_id=actor_id,
    )
    session.add(operation)
    await session.commit()
    return operation


async def finalize_invite_revocation(
    session: AsyncSession,
    operation_id: int,
) -> bool:
    operation = await session.scalar(
        select(InviteOperation)
        .where(InviteOperation.id == operation_id)
        .with_for_update()
    )
    if operation is None or operation.operation != "revoke":
        return False
    campaign = await session.get(InviteCampaign, operation.campaign_id) if operation.campaign_id else None
    if campaign is not None:
        campaign.active = False
    operation.status = "completed"
    operation.error_text = None
    await session.commit()
    return True


async def mark_invite_revocation_uncertain(
    session: AsyncSession,
    operation_id: int,
    error_text: str,
) -> None:
    operation = await session.get(InviteOperation, operation_id)
    if operation is None:
        return
    operation.status = REVOKE_UNCERTAIN
    operation.error_text = error_text[:1000]
    await session.commit()


def _invite_operation_is_stale(operation: InviteOperation, now: datetime) -> bool:
    freshness = operation.updated_at or operation.created_at
    return freshness is None or freshness <= now - INVITE_OPERATION_STALE_AFTER


async def recover_invite_operations() -> None:
    """Quarantine only stale invite operations; never steal a fresh live claim."""
    cutoff = datetime.now(timezone.utc) - INVITE_OPERATION_STALE_AFTER
    freshness = func.coalesce(InviteOperation.updated_at, InviteOperation.created_at)
    async with SessionFactory() as session:
        ids = list((await session.scalars(
            select(InviteOperation.id).where(
                InviteOperation.status.in_([CREATE_IN_PROGRESS, REVOKE_IN_PROGRESS]),
                or_(freshness.is_(None), freshness <= cutoff),
            )
        )).all())

    for operation_id in ids:
        async with SessionFactory() as session:
            group_id = await session.scalar(
                select(InviteOperation.group_id).where(InviteOperation.id == operation_id)
            )
            if group_id is None:
                continue
            await session.scalar(
                select(Group).where(Group.id == group_id).with_for_update()
            )
            operation = await session.scalar(
                select(InviteOperation)
                .where(InviteOperation.id == operation_id)
                .with_for_update()
            )
            if operation is None or operation.status not in {CREATE_IN_PROGRESS, REVOKE_IN_PROGRESS}:
                continue
            if not _invite_operation_is_stale(operation, datetime.now(timezone.utc)):
                continue
            if operation.status == CREATE_IN_PROGRESS:
                operation.status = CREATE_UNCERTAIN
                operation.error_text = (
                    "Процесс прервался во время создания ссылки; Telegram мог создать ссылку, "
                    "но её URL не был сохранён Mimoru."
                )
            else:
                operation.status = REVOKE_UNCERTAIN
                operation.error_text = (
                    "Процесс прервался во время отзыва ссылки; Telegram мог уже отозвать её. "
                    "Повторите отключение для безопасной проверки/повтора."
                )
            await session.commit()
