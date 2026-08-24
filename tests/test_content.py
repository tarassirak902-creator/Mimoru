import pytest

from app.services.content import contains_blocked_link, extract_domains, normalize_domain


def test_normalize_domain():
    assert normalize_domain("https://WWW.Example.com/path?q=1") == "example.com"
    assert normalize_domain("t.me/channel") == "t.me"


def test_extract_domains():
    assert extract_domains("Смотрите https://example.com/a и t.me/test") == {"example.com", "t.me"}


def test_whitelist_allows_subdomains():
    assert not contains_blocked_link("https://shop.example.com/item", {"example.com"})


def test_non_whitelisted_link_is_blocked():
    assert contains_blocked_link("https://evil.example/path", {"example.com"})


def test_invalid_domain():
    with pytest.raises(ValueError):
        normalize_domain("localhost")
