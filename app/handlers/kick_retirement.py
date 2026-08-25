from __future__ import annotations

import sys

from aiogram import F, Router
from aiogram.types import CallbackQuery

router = Router(name=__name__)


def _replace_loaded_text(module_name: str, attribute: str, replacements: tuple[tuple[str, str], ...]) -> None:
    module = sys.modules.get(module_name)
    if module is None:
        return
    text = getattr(module, attribute, None)
    if not isinstance(text, str):
        return
    for old, new in replacements:
        text = text.replace(old, new)
    setattr(module, attribute, text)


def _retire_kick_from_legacy_help() -> None:
    """Remove kick instructions from the legacy secondary panel help."""
    _replace_loaded_text(
        "app.handlers.panel",
        "COMMANDS_TEXT",
        (
            (
                "<code>размут</code>, <code>кик</code>, <code>пред</code>, ",
                "<code>размут</code>, <code>пред</code>, ",
            ),
            (
                "Для предупреждения, мута, кика и бана Mimoru предложит причины кнопками.",
                "Для предупреждения, мута и бана Mimoru предложит причины кнопками.",
            ),
        ),
    )


_retire_kick_from_legacy_help()


@router.callback_query(
    F.data.regexp(
        r"^(?:reason_action:\d+:\d+:kick|member_punish:\d+:-?\d+:kick|role_perm:\d+:\d+:kick)$"
    )
)
async def retired_kick_callback(callback: CallbackQuery) -> None:
    await callback.answer(
        "Кик отключён в Mimoru. Используйте предупреждение, мут или бан.",
        show_alert=True,
    )
