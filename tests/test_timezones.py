from datetime import datetime, timezone

import pytest

from app.services.timezones import to_local, to_utc, validate_timezone


def test_timezone_roundtrip():
    local = datetime(2026, 8, 3, 12, 0)
    utc = to_utc(local, "Europe/Warsaw")
    assert utc == datetime(2026, 8, 3, 10, 0, tzinfo=timezone.utc)
    assert to_local(utc, "Europe/Warsaw").hour == 12


def test_invalid_timezone():
    with pytest.raises(ValueError):
        validate_timezone("Mars/Olympus")
