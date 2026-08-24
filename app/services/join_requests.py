from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InviteCommand:
    name: str
    creates_join_request: bool


def parse_invite_command(text: str) -> InviteCommand | None:
    normalized = " ".join(text.strip().split())
    lowered = normalized.casefold()
    prefixes = {
        "создать ссылку ": False,
        "создать ссылку-заявку ": True,
        "создать ссылку заявку ": True,
    }
    for prefix, creates_request in prefixes.items():
        if lowered.startswith(prefix):
            name = normalized[len(prefix):].strip()
            if 1 <= len(name) <= 64:
                return InviteCommand(name=name, creates_join_request=creates_request)
    return None


def normalize_invite_link(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip()


def join_request_status_label(status: str) -> str:
    return {
        "pending": "ожидает",
        "processing_approve": "одобрение выполняется",
        "processing_decline": "отклонение выполняется",
        "review_uncertain": "результат требует проверки",
        "approved": "одобрена",
        "declined": "отклонена",
        "expired": "истекла",
    }.get(status, status)