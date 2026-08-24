import pytest

from app.services.slow_mode import normalize_slow_mode_seconds, remaining_seconds, slow_mode_key


def test_slow_mode_limits():
    assert normalize_slow_mode_seconds(3) == 3
    assert normalize_slow_mode_seconds(3600) == 3600
    with pytest.raises(ValueError):
        normalize_slow_mode_seconds(2)
    with pytest.raises(ValueError):
        normalize_slow_mode_seconds(3601)


def test_slow_mode_key_and_ttl():
    assert slow_mode_key(-100, 42) == "slowmode:-100:42"
    assert remaining_seconds(-1) == 0
    assert remaining_seconds(8) == 8
