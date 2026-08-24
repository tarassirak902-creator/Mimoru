from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "Europe/Warsaw"


def validate_timezone(name: str) -> str:
    value = name.strip()
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Неизвестный часовой пояс. Пример: Europe/Warsaw") from exc
    return value


def to_utc(local_dt: datetime, timezone_name: str) -> datetime:
    zone = ZoneInfo(validate_timezone(timezone_name))
    if local_dt.tzinfo is None:
        local_dt = local_dt.replace(tzinfo=zone)
    else:
        local_dt = local_dt.astimezone(zone)
    return local_dt.astimezone(timezone.utc)


def to_local(utc_dt: datetime, timezone_name: str) -> datetime:
    zone = ZoneInfo(validate_timezone(timezone_name))
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(zone)
