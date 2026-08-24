from __future__ import annotations

import re

MENTION_RE = re.compile(r"(?<![\w@])@[A-Za-z0-9_]{5,32}\b")
TG_USER_RE = re.compile(r"tg://user\?id=\d+")
HASHTAG_RE = re.compile(r"(?<!\w)#[\w\d_]{2,64}", re.UNICODE)


def count_mentions_and_hashtags(text: str) -> tuple[int, int]:
    """Return unique mention-like references and hashtags in message text."""
    mentions = {item.casefold() for item in MENTION_RE.findall(text or "")}
    mentions.update(item.casefold() for item in TG_USER_RE.findall(text or ""))
    hashtags = {item.casefold() for item in HASHTAG_RE.findall(text or "")}
    return len(mentions), len(hashtags)


def normalize_mention_limit(value: int) -> int:
    if not 1 <= value <= 50:
        raise ValueError("Лимит упоминаний должен быть от 1 до 50.")
    return value


def normalize_hashtag_limit(value: int) -> int:
    if not 1 <= value <= 100:
        raise ValueError("Лимит хэштегов должен быть от 1 до 100.")
    return value


def normalize_mention_mute(value: int) -> int:
    if not 60 <= value <= 30 * 86400:
        raise ValueError("Срок мута должен быть от 1 минуты до 30 дней.")
    return value
