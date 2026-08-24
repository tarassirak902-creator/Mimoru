import pytest

from app.services.campaign_spam import (
    build_campaign_signature,
    normalize_campaign_limit,
    normalize_campaign_mute,
    normalize_campaign_text,
    normalize_campaign_window,
)


def test_signature_matches_normalized_text() -> None:
    first = build_campaign_signature("  КУПИ сейчас https://example.com!!! ")
    second = build_campaign_signature("купи сейчас https://example.com")
    assert first == second
    assert first is not None


def test_short_common_text_is_ignored() -> None:
    assert build_campaign_signature("спасибо") is None
    assert build_campaign_signature("ок", ["file-123"]) is not None


def test_media_order_does_not_change_signature() -> None:
    assert build_campaign_signature(None, ["b", "a"]) == build_campaign_signature(None, ["a", "b"])


def test_campaign_limits() -> None:
    assert normalize_campaign_limit(3) == 3
    assert normalize_campaign_window(120) == 120
    assert normalize_campaign_mute(3600) == 3600
    with pytest.raises(ValueError):
        normalize_campaign_limit(1)
    with pytest.raises(ValueError):
        normalize_campaign_window(5)
    with pytest.raises(ValueError):
        normalize_campaign_mute(30)
