from typing import Any


def sender_chat_id(message: Any) -> int | None:
    return message.sender_chat.id if message.sender_chat else None


def is_group_identity(message: Any) -> bool:
    return bool(message.sender_chat and message.sender_chat.id == message.chat.id)
