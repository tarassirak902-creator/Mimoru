import pytest

from app.services.mentions import (
    count_mentions_and_hashtags,
    normalize_hashtag_limit,
    normalize_mention_limit,
    normalize_mention_mute,
)


def test_count_unique_mentions_and_hashtags() -> None:
    mentions, hashtags = count_mentions_and_hashtags(
        "@User_one @user_one @SecondUser #Sale #sale #Новости tg://user?id=123"
    )
    assert mentions == 3
    assert hashtags == 2


def test_normalize_limits() -> None:
    assert normalize_mention_limit(5) == 5
    assert normalize_hashtag_limit(10) == 10
    assert normalize_mention_mute(1800) == 1800


@pytest.mark.parametrize("value", [0, 51])
def test_invalid_mention_limit(value: int) -> None:
    with pytest.raises(ValueError):
        normalize_mention_limit(value)
