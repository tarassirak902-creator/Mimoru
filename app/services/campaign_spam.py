from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

_URL_RE = re.compile(r"(?:https?://|t\.me/|www\.)\S+", re.IGNORECASE)


def normalize_campaign_text(value: str) -> str:
    """Normalize text while preserving enough information to identify campaigns."""
    text = " ".join(value.casefold().replace("ё", "е").split())
    # Strip common trailing punctuation used to evade exact duplicate checks.
    return text.strip(" .,!?:;—–-_")


def build_campaign_signature(text: str | None, media_unique_ids: Iterable[str] = ()) -> str | None:
    normalized = normalize_campaign_text(text or "")
    media = sorted(item for item in media_unique_ids if item)
    if not normalized and not media:
        return None

    # Very short ordinary messages are too common to be useful campaign indicators.
    has_url = bool(_URL_RE.search(normalized))
    if normalized and len(normalized) < 12 and not has_url and not media:
        return None

    payload = "text=" + normalized + "|media=" + "|".join(media)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def normalize_campaign_limit(value: int) -> int:
    if not 2 <= value <= 20:
        raise ValueError("Лимит массового спама должен быть от 2 до 20 пользователей")
    return value


def normalize_campaign_window(value: int) -> int:
    if not 10 <= value <= 3600:
        raise ValueError("Окно массового спама должно быть от 10 секунд до 1 часа")
    return value


def normalize_campaign_mute(value: int) -> int:
    if not 60 <= value <= 30 * 86400:
        raise ValueError("Срок наказания должен быть от 1 минуты до 30 дней")
    return value
