from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SENSITIVE_FRAGMENTS = (
    "token",
    "password",
    "secret",
    "authorization",
    "cookie",
    "api_key",
    "apikey",
    "private_key",
)
REDACTED = "[REDACTED]"
MAX_DEPTH = 8


def is_sensitive_key(key: object) -> bool:
    normalized = str(key).strip().lower().replace("-", "_")
    return any(fragment in normalized for fragment in SENSITIVE_FRAGMENTS)


def redact_value(value: Any, *, depth: int = 0) -> Any:
    if depth >= MAX_DEPTH:
        return "[MAX_DEPTH]"
    if isinstance(value, Mapping):
        return {
            key: REDACTED if is_sensitive_key(key) else redact_value(item, depth=depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_value(item, depth=depth + 1) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item, depth=depth + 1) for item in value)
    return value


def redact_event_dict(_logger: object, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    return redact_value(event_dict)
