from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


SLOW_UPDATE_THRESHOLD_MS = 750


def _event_context(event: TelegramObject) -> dict[str, Any]:
    context: dict[str, Any] = {"event_type": type(event).__name__}

    from_user = getattr(event, "from_user", None)
    if from_user is not None:
        context["user_id"] = from_user.id

    chat = getattr(event, "chat", None)
    if chat is None and isinstance(event, CallbackQuery) and event.message is not None:
        chat = event.message.chat
    if chat is not None:
        context["chat_id"] = chat.id
        context["chat_type"] = chat.type

    if isinstance(event, CallbackQuery):
        data = event.data or ""
        context["callback_prefix"] = data.split(":", 1)[0][:64] if data else None
    elif isinstance(event, Message):
        context["message_kind"] = (
            "command"
            if isinstance(event.text, str) and event.text.startswith("/")
            else "text"
            if event.text is not None
            else "media"
        )

    return context


class SlowUpdateLoggingMiddleware(BaseMiddleware):
    """Log only unusually slow Telegram updates without recording message text."""

    def __init__(self, threshold_ms: int = SLOW_UPDATE_THRESHOLD_MS) -> None:
        self.threshold_ms = threshold_ms
        self.log = structlog.get_logger()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        started = time.perf_counter()
        try:
            return await handler(event, data)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000)
            if duration_ms >= self.threshold_ms:
                self.log.warning(
                    "slow_update",
                    duration_ms=duration_ms,
                    threshold_ms=self.threshold_ms,
                    **_event_context(event),
                )
