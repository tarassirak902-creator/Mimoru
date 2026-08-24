from datetime import datetime, timedelta, timezone

from app.services.scheduling import next_occurrence, parse_scheduled_message


def test_daily_schedule_parse():
    send_at, text, recurrence, weekday, recurrence_time = parse_scheduled_message(
        "запланировать ежедневно 12:30 | Новости", "Europe/Warsaw"
    )
    assert send_at.tzinfo is not None
    assert text == "Новости"
    assert recurrence == "daily"
    assert weekday is None
    assert recurrence_time == "12:30"


def test_weekly_next_occurrence():
    current = datetime(2026, 8, 3, 10, 0, tzinfo=timezone.utc)
    assert next_occurrence(current, "weekly") == current + timedelta(days=7)
