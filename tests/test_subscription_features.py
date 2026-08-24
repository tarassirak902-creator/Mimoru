from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.plans import feature_available, paid_plan, plan_limit, remaining_days, subscription_state


def group(code: str, days: int | None):
    expires = None if days is None else datetime.now(timezone.utc) + timedelta(days=days)
    return SimpleNamespace(plan_code=code, plan_expires_at=expires)


def test_free_has_basic_limits_and_no_commercial_marketplace():
    g = group("free", None)
    assert plan_limit(g, "channels") == 5
    assert plan_limit(g, "moderators") == 1_000_000
    assert plan_limit(g, "reasons") == 5
    assert not feature_available(g, "ads_marketplace")


def test_standard_unlocks_reports_and_ads():
    g = group("standard", 20)
    assert feature_available(g, "daily_reports")
    assert feature_available(g, "advanced_analytics")
    assert feature_available(g, "ads_marketplace")


def test_trial_does_not_unlock_commercial_marketplace():
    g = group("trial", 3)
    assert feature_available(g, "daily_reports")
    assert not feature_available(g, "ads_marketplace")


def test_pro_has_max_config_limits_without_admin_or_op_tariff_gating():
    g = group("pro", 10)
    assert plan_limit(g, "words") == 1000
    assert plan_limit(g, "channels") == 5
    assert plan_limit(g, "moderators") == 1_000_000
    assert plan_limit(g, "reasons") == 100


def test_subscription_state_and_remaining_days():
    now = datetime.now(timezone.utc)
    g = SimpleNamespace(plan_code="pro", plan_expires_at=now + timedelta(hours=25))
    assert subscription_state(g, now=now) == "active"
    assert remaining_days(g, now=now) == 2
    expired = SimpleNamespace(plan_code="pro", plan_expires_at=now - timedelta(seconds=1))
    assert subscription_state(expired, now=now) == "expired"
    assert remaining_days(expired, now=now) == 0


def test_paid_plan_catalog_is_canonical():
    assert paid_plan("standard")["stars"] == 250
    assert paid_plan("pro")["stars"] == 500
