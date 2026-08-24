from datetime import datetime, timedelta, timezone

from app.services.quarantine import is_quarantine_active, quarantine_until


def test_quarantine_active_inside_window():
    joined = datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc)
    assert is_quarantine_active(joined, 3600, joined + timedelta(minutes=30))
    assert not is_quarantine_active(joined, 3600, joined + timedelta(hours=1))


def test_quarantine_until_handles_naive_datetime():
    joined = datetime(2026, 8, 2, 10, 0)
    result = quarantine_until(joined, 600)
    assert result.tzinfo is not None
    assert result.minute == 10
