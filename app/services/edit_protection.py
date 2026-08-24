from datetime import datetime, timezone


def normalize_edit_window(seconds: int) -> int:
    if seconds < 300:
        raise ValueError("Окно проверки не может быть меньше 5 минут.")
    if seconds > 2_592_000:
        raise ValueError("Окно проверки не может быть больше 30 дней.")
    return seconds


def should_recheck_edit(
    original_date: datetime,
    edit_date: datetime | None,
    window_seconds: int,
    *,
    now: datetime | None = None,
) -> bool:
    if edit_date is None:
        return False
    current = now or datetime.now(timezone.utc)
    if original_date.tzinfo is None:
        original_date = original_date.replace(tzinfo=timezone.utc)
    return (current - original_date).total_seconds() <= window_seconds
