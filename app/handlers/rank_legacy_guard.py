from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.services.ui import panel_header


router = Router(name=__name__)


@router.callback_query(F.data.regexp(r"^role_(add|edit|set|perm|reset|toggle|remove|remove_confirm):\d+(?::.*)?$"))
async def legacy_role_button(callback: CallbackQuery) -> None:
    """Redirect already-sent buttons from the retired role UI."""
    parts = callback.data.split(":")
    try:
        group_id = int(parts[1])
    except (IndexError, ValueError):
        await callback.answer("Старая кнопка больше не поддерживается.", show_alert=True)
        return
    await callback.message.edit_text(
        panel_header(
            "Система рангов обновлена",
            "Эта кнопка относится к старой версии ролей. Откройте актуальный раздел рангов — существующие старые роли перенесены автоматически.",
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 Открыть ранги", callback_data=f"roles:{group_id}")],
            [InlineKeyboardButton(text="◀️ К модерации", callback_data=f"group_section:{group_id}:moderation")],
        ]),
    )
    await callback.answer()
