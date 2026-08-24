from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.methods.base import TelegramMethod


_IDEMPOTENT_EDIT_METHODS = {
    "EditMessageText",
    "EditMessageCaption",
    "EditMessageMedia",
    "EditMessageReplyMarkup",
}


def is_idempotent_edit_error(method: TelegramMethod[object], exc: TelegramBadRequest) -> bool:
    """Return True only for Telegram's harmless repeated edit response.

    The caller may treat this as an already-applied state. All unrelated
    TelegramBadRequest errors must still propagate.
    """
    return (
        type(method).__name__ in _IDEMPOTENT_EDIT_METHODS
        and "message is not modified" in str(exc).casefold()
    )
