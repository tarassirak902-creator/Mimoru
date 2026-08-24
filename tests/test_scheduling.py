from datetime import datetime, timedelta, timezone

import pytest

from app.services import scheduling


def test_parse_scheduled_message(monkeypatch):
    future = datetime.now(timezone.utc) + timedelta(days=2)
    text = f"запланировать {future:%Y-%m-%d %H:%M} | Привет группе"
    send_at, body, recurrence, weekday, recurrence_time = scheduling.parse_scheduled_message(text, "UTC")
    assert send_at.tzinfo is not None
    assert body == "Привет группе"
    assert recurrence == "once"
    assert weekday is None


def test_schedule_requires_separator():
    with pytest.raises(ValueError):
        scheduling.parse_scheduled_message("запланировать 2030-01-01 12:00 текст")


def test_schedule_rejects_past():
    with pytest.raises(ValueError):
        scheduling.parse_scheduled_message("запланировать 2020-01-01 12:00 | текст")
