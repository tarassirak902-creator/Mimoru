from __future__ import annotations


def normalize_slow_mode_seconds(value: int) -> int:
    """Validate application-level slow mode delay.

    A small lower bound prevents accidental message storms; the upper bound keeps
    the feature suitable for chat moderation rather than long-term restrictions.
    """
    if not 3 <= value <= 3600:
        raise ValueError("Срок медленного режима должен быть от 3 секунд до 1 часа")
    return value


def slow_mode_key(chat_id: int, user_id: int) -> str:
    return f"slowmode:{chat_id}:{user_id}"


def remaining_seconds(ttl: int) -> int:
    """Convert Redis TTL to a user-facing non-negative value."""
    return max(0, ttl)
