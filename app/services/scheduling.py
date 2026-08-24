from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from app.services.timezones import to_utc

ONCE_RE = re.compile(
    r"^запланировать\s+(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})\s*\|\s*(.+)$",
    re.IGNORECASE | re.DOTALL,
)
DAILY_RE = re.compile(r"^запланировать\s+ежедневно\s+(\d{1,2}:\d{2})\s*\|\s*(.+)$", re.IGNORECASE | re.DOTALL)
WEEKLY_RE = re.compile(
    r"^запланировать\s+еженедельно\s+(пн|вт|ср|чт|пт|сб|вс)\s+(\d{1,2}:\d{2})\s*\|\s*(.+)$",
    re.IGNORECASE | re.DOTALL,
)
WEEKDAYS = {"пн": 0, "вт": 1, "ср": 2, "чт": 3, "пт": 4, "сб": 5, "вс": 6}


def _validate_body(body: str) -> str:
    body = body.strip()
    if not body:
        raise ValueError("Текст публикации не может быть пустым")
    if len(body) > 4096:
        raise ValueError("Текст публикации длиннее 4096 символов")
    return body


def _parse_hm(value: str) -> tuple[int, int]:
    try:
        hour, minute = map(int, value.split(":"))
    except (ValueError, AttributeError) as exc:
        raise ValueError("Некорректное время") from exc
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Некорректное время")
    return hour, minute


def parse_scheduled_message(text: str, timezone_name: str = "Europe/Warsaw") -> tuple[datetime, str, str, int | None, str | None]:
    value = text.strip()
    match = ONCE_RE.match(value)
    if match:
        date_part, time_part, body = match.groups()
        try:
            local_dt = datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M")
        except ValueError as exc:
            raise ValueError("Некорректная дата или время") from exc
        send_at = to_utc(local_dt, timezone_name)
        if send_at <= datetime.now(timezone.utc):
            raise ValueError("Дата публикации должна быть в будущем")
        return send_at, _validate_body(body), "once", None, time_part.zfill(5)

    match = DAILY_RE.match(value)
    if match:
        time_part, body = match.groups()
        hour, minute = _parse_hm(time_part)
        now_local = datetime.now(timezone.utc).astimezone(__import__('zoneinfo').ZoneInfo(timezone_name))
        candidate = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now_local:
            candidate += timedelta(days=1)
        return candidate.astimezone(timezone.utc), _validate_body(body), "daily", None, f"{hour:02d}:{minute:02d}"

    match = WEEKLY_RE.match(value)
    if match:
        weekday_raw, time_part, body = match.groups()
        hour, minute = _parse_hm(time_part)
        weekday = WEEKDAYS[weekday_raw.casefold()]
        now_local = datetime.now(timezone.utc).astimezone(__import__('zoneinfo').ZoneInfo(timezone_name))
        days = (weekday - now_local.weekday()) % 7
        candidate = (now_local + timedelta(days=days)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now_local:
            candidate += timedelta(days=7)
        return candidate.astimezone(timezone.utc), _validate_body(body), "weekly", weekday, f"{hour:02d}:{minute:02d}"

    raise ValueError(
        "Форматы:\n"
        "запланировать ГГГГ-ММ-ДД ЧЧ:ММ | текст\n"
        "запланировать ежедневно ЧЧ:ММ | текст\n"
        "запланировать еженедельно пн ЧЧ:ММ | текст"
    )


def next_occurrence(current_utc: datetime, recurrence: str) -> datetime | None:
    if recurrence == "daily":
        return current_utc + timedelta(days=1)
    if recurrence == "weekly":
        return current_utc + timedelta(days=7)
    return None
