from datetime import datetime, timedelta, timezone


def should_force_verification(join_count: int, limit: int, enabled: bool) -> bool:
    return enabled and limit > 0 and join_count > limit


def warning_expiry_cutoff(days: int, now: datetime | None = None) -> datetime | None:
    if days <= 0:
        return None
    current = now or datetime.now(timezone.utc)
    return current - timedelta(days=days)
