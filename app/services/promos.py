from __future__ import annotations

from datetime import datetime, timedelta, timezone


def normalize_promo_code(value: str) -> str:
    return "".join(value.strip().upper().split())


def promo_is_available(*, active: bool, expires_at: datetime | None, current_uses: int, max_uses: int, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    if not active or current_uses >= max_uses:
        return False
    return expires_at is None or expires_at > now


def extend_plan(current_expiry: datetime | None, days: int, now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    start = current_expiry if current_expiry and current_expiry > now else now
    return start + timedelta(days=days)
