from __future__ import annotations

from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.invite_operation_models import InviteOperation
from app.db.models import Group, InviteCampaign
from app.services.access import is_service_owner
from app.services.join_request_transitions import (
    CREATE_IN_PROGRESS,
    CREATE_UNCERTAIN,
    REVOKE_IN_PROGRESS,
    REVOKE_UNCERTAIN,
)


@dataclass(slots=True)
class InviteExecutionResult:
    status: str
    campaign_id: int | None = None
    invite_link: str | None = None
    error_text: str | None = None


def _actor_still_authorized(group: Group, actor_id: int) -> bool:
    return group.owner_telegram_id == actor_id or is_service_owner(actor_id)


async def _locked_group_and_operation(
    session: AsyncSession,
    operation_id: int,
) -> tuple[Group | None, InviteOperation | None]:
    group_id = await session.scalar(
        select(InviteOperation.group_id).where(InviteOperation.id == operation_id)
    )
    if group_id is None:
        return None, None
    group = await session.scalar(
        select(Group).where(Group.id == group_id).with_for_update()
    )
    operation = await session.scalar(
        select(InviteOperation).where(InviteOperation.id == operation_id).with_for_update()
    )
    return group, operation


async def execute_invite_creation(
    session: AsyncSession,
    bot: Bot,
    *,
    operation_id: int,
) -> InviteExecutionResult:
    group, operation = await _locked_group_and_operation(session, operation_id)
    if (
        group is None
        or operation is None
        or operation.operation != "create"
        or operation.status != CREATE_IN_PROGRESS
        or operation.name is None
    ):
        return InviteExecutionResult("not_pending")

    if not group.is_active:
        operation.status = "failed"
        operation.error_text = "Группа неактивна"
        await session.commit()
        return InviteExecutionResult("inactive", error_text=operation.error_text)

    if not _actor_still_authorized(group, operation.actor_telegram_id):
        operation.status = "cancelled"
        operation.error_text = "Создатель операции больше не управляет группой"
        await session.commit()
        return InviteExecutionResult("stale_actor", error_text=operation.error_text)

    try:
        link = await bot.create_chat_invite_link(
            chat_id=group.telegram_chat_id,
            name=operation.name,
            creates_join_request=bool(operation.creates_join_request),
        )
    except (TelegramBadRequest, TelegramForbiddenError) as error:
        operation.status = "failed"
        operation.error_text = str(error)[:1000]
        await session.commit()
        return InviteExecutionResult("telegram_error", error_text=operation.error_text)

    campaign = InviteCampaign(
        group_id=operation.group_id,
        name=operation.name,
        invite_link=link.invite_link,
        creates_join_request=bool(operation.creates_join_request),
        created_by_telegram_id=operation.actor_telegram_id,
    )
    try:
        async with session.begin_nested():
            session.add(campaign)
            await session.flush()
    except IntegrityError as error:
        compensated = False
        compensation_error = str(error)
        try:
            await bot.revoke_chat_invite_link(group.telegram_chat_id, link.invite_link)
            compensated = True
        except (TelegramBadRequest, TelegramForbiddenError) as revoke_error:
            compensation_error = f"{error}; revoke: {revoke_error}"
        operation.invite_link = link.invite_link
        operation.status = "compensated" if compensated else CREATE_UNCERTAIN
        operation.error_text = None if compensated else compensation_error[:1000]
        await session.commit()
        return InviteExecutionResult(
            "compensated" if compensated else "uncertain",
            invite_link=link.invite_link,
            error_text=operation.error_text,
        )

    operation.campaign_id = campaign.id
    operation.invite_link = link.invite_link
    operation.status = "completed"
    operation.error_text = None
    await session.commit()
    return InviteExecutionResult(
        "completed",
        campaign_id=campaign.id,
        invite_link=link.invite_link,
    )


async def execute_invite_revocation(
    session: AsyncSession,
    bot: Bot,
    *,
    operation_id: int,
) -> InviteExecutionResult:
    group, operation = await _locked_group_and_operation(session, operation_id)
    if (
        group is None
        or operation is None
        or operation.operation != "revoke"
        or operation.status != REVOKE_IN_PROGRESS
        or operation.campaign_id is None
    ):
        return InviteExecutionResult("not_pending")

    campaign = await session.scalar(
        select(InviteCampaign)
        .where(InviteCampaign.id == operation.campaign_id)
        .with_for_update()
    )
    if campaign is None:
        operation.status = "failed"
        operation.error_text = "Кампания ссылки не найдена"
        await session.commit()
        return InviteExecutionResult("missing_campaign", campaign_id=operation.campaign_id)

    if not group.is_active:
        operation.status = "failed"
        operation.error_text = "Группа неактивна"
        await session.commit()
        return InviteExecutionResult("inactive", campaign_id=campaign.id, error_text=operation.error_text)

    if not _actor_still_authorized(group, operation.actor_telegram_id):
        operation.status = "cancelled"
        operation.error_text = "Создатель операции больше не управляет группой"
        await session.commit()
        return InviteExecutionResult("stale_actor", campaign_id=campaign.id, error_text=operation.error_text)

    if not campaign.active:
        operation.status = "completed"
        operation.error_text = None
        await session.commit()
        return InviteExecutionResult("completed", campaign_id=campaign.id)

    invite_link = operation.invite_link or campaign.invite_link
    try:
        await bot.revoke_chat_invite_link(group.telegram_chat_id, invite_link)
    except (TelegramBadRequest, TelegramForbiddenError) as error:
        operation.status = REVOKE_UNCERTAIN
        operation.error_text = str(error)[:1000]
        await session.commit()
        return InviteExecutionResult(
            "uncertain",
            campaign_id=campaign.id,
            invite_link=invite_link,
            error_text=operation.error_text,
        )

    campaign.active = False
    operation.status = "completed"
    operation.error_text = None
    await session.commit()
    return InviteExecutionResult(
        "completed",
        campaign_id=campaign.id,
        invite_link=invite_link,
    )
