from __future__ import annotations

from datetime import time


def parse_hhmm(value: str) -> time:
    parts = value.strip().split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError("Время должно быть в формате ЧЧ:ММ")
    hour, minute = map(int, parts)
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Некорректное время")
    return time(hour=hour, minute=minute)


def is_night_window(current: time, start: time, end: time) -> bool:
    """Return whether current time falls inside [start, end).

    Supports both same-day windows (e.g. 13:00-18:00) and windows crossing
    midnight (e.g. 23:00-07:00). Equal start/end means a full-day window.
    """
    if start == end:
        return True
    if start < end:
        return start <= current < end
    return current >= start or current < end
