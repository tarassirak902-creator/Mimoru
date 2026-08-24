from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from redis.asyncio import Redis


CANCELLED_REPLY_KEY = "mimoru:cancelled-reply:{user_id}:{message_id}"


class CancelledReplyMiddleware(BaseMiddleware):
    """Stop stale replies to a cancelled private-chat ForceReply prompt."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if (
            isinstance(event, Message)
            and event.chat.type == "private"
            and event.from_user is not None
            and event.reply_to_message is not None
        ):
            key = CANCELLED_REPLY_KEY.format(
                user_id=event.from_user.id,
                message_id=event.reply_to_message.message_id,
            )
            if await self.redis.exists(key):
                await event.answer("Этот ввод уже отменён. Ничего не сохранено.")
                return None
        return await handler(event, data)
