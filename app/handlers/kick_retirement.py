from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

router = Router(name=__name__)


@router.callback_query(
    F.data.regexp(
        r"^(?:reason_action:\d+:\d+:kick|member_punish:\d+:-?\d+:kick|role_perm:\d+:\d+:kick)$"
    )
)
async def retired_kick_callback(callback: CallbackQuery) -> None:
    """Keep already-sent legacy kick buttons from failing silently."""
    await callback.answer(
        "Кик отключён в Mimoru. Используйте предупреждение, мут или бан.",
        show_alert=True,
    )
