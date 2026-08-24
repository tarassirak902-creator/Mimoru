from datetime import time

import pytest

from app.services.night_mode import is_night_window, parse_hhmm


def test_parse_hhmm() -> None:
    assert parse_hhmm("23:15") == time(23, 15)
    with pytest.raises(ValueError):
        parse_hhmm("25:00")


def test_window_crossing_midnight() -> None:
    assert is_night_window(time(23, 30), time(23), time(7))
    assert is_night_window(time(6, 59), time(23), time(7))
    assert not is_night_window(time(12), time(23), time(7))


def test_same_day_window() -> None:
    assert is_night_window(time(14), time(13), time(18))
    assert not is_night_window(time(19), time(13), time(18))
