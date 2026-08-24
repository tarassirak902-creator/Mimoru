from datetime import datetime, timedelta, timezone


def quarantine_until(joined_at: datetime, duration_seconds: int) -> datetime:
    if joined_at.tzinfo is None:
        joined_at = joined_at.replace(tzinfo=timezone.utc)
    return joined_at + timedelta(seconds=max(0, duration_seconds))


def is_quarantine_active(
    joined_at: datetime,
    duration_seconds: int,
    now: datetime | None = None,
) -> bool:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return duration_seconds > 0 and now < quarantine_until(joined_at, duration_seconds)
