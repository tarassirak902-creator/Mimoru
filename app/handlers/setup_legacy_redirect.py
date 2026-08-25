from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group
from app.handlers.wizard_navigation import _profile_menu, _wizard_text
from app.services.access import is_service_owner

router = Router(name=__name__)


async def _owned_group(session: AsyncSession, group_id: int, user_id: int) -> Group | None:
    query = select(Group).where(Group.id == group_id, Group.is_active.is_(True))
    if not is_service_owner(user_id):
        query = query.where(Group.owner_telegram_id == user_id)
    return await session.scalar(query)


# Buttons from messages created by the old wizard can remain in Telegram for a
# long time. Their later steps did not encode enough context to support true
# one-step back navigation. Rather than let an old button reopen that broken
# flow, restart the current reversible wizard explicitly.
@router.callback_query(
    F.data.regexp(
        r"^setup:\d+:(?:"
        r"type:(?:community|gaming|crypto|sales|news|education)|"
        r"level:(?:community|gaming|crypto|sales|news|education):(?:minimal|standard|maximum)|"
        r"captcha:(?:on|off)|welcome:(?:on|off)|quarantine:(?:on|off)|reports:(?:on|off)"
        r")$"
    )
)
async def redirect_stale_wizard_button(callback: CallbackQuery, session: AsyncSession) -> None:
    group_id = int(callback.data.split(":")[1])
    group = await _owned_group(session, group_id, callback.from_user.id)
    if group is None:
        await callback.answer("Группа недоступна или нет доступа.", show_alert=True)
        return
    await callback.message.edit_text(
        _wizard_text(group, 1, "Какой это тип сообщества?"),
        reply_markup=_profile_menu(group.id),
    )
    await callback.answer("Этот старый экран обновлён. Продолжите настройку в новом мастере.")
