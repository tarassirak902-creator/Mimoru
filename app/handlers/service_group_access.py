from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.service_management import group_card
from app.services.access import is_service_owner
from app.services.client_access import set_group_service_active


router = Router(name=__name__)


@router.callback_query(F.data.regexp(r"^service_group_action:\d+:(enable|disable)$"))
async def group_action_serialized(callback: CallbackQuery, session: AsyncSession) -> None:
    """Own the service group mutation before the legacy management router."""
    if not is_service_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    _, raw_group_id, action = callback.data.split(":")
    result = await set_group_service_active(
        session,
        group_id=int(raw_group_id),
        active=action == "enable",
    )
    if result.group is None:
        await callback.answer("Группа не найдена.", show_alert=True)
        return
    if result.blocked_owner:
        await callback.answer("Сначала разблокируйте клиента-владельца группы.", show_alert=True)
        return

    callback.data = f"service_group:{result.group.id}"
    await group_card(callback, session)
