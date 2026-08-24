from app.utils.duration import parse_duration, human_duration


def test_parse_duration_common_values():
    assert parse_duration('1м') == 60
    assert parse_duration('5мин') == 300
    assert parse_duration('2ч') == 7200
    assert parse_duration('1д') == 86400


def test_parse_duration_rejects_bad_values():
    assert parse_duration('') is None
    assert parse_duration('минута') is None
    assert parse_duration('0.5ч') is None


def test_human_duration_minute():
    assert human_duration(60) == '1 мин.'
