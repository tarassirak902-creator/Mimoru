from datetime import datetime, timedelta, timezone

from app.services.promos import extend_plan, normalize_promo_code, promo_is_available


def test_normalize_promo_code():
    assert normalize_promo_code("  start-7 ") == "START-7"


def test_promo_availability():
    now = datetime.now(timezone.utc)
    assert promo_is_available(active=True, expires_at=now + timedelta(days=1), current_uses=0, max_uses=1, now=now)
    assert not promo_is_available(active=True, expires_at=now - timedelta(seconds=1), current_uses=0, max_uses=1, now=now)
    assert not promo_is_available(active=True, expires_at=None, current_uses=1, max_uses=1, now=now)


def test_extend_plan_uses_future_expiry():
    now = datetime.now(timezone.utc)
    current = now + timedelta(days=5)
    assert extend_plan(current, 2, now=now) == current + timedelta(days=2)
