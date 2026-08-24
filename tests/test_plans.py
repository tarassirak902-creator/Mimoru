from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

from app.services.plans import effective_plan, plan_limit


def test_expired_plan_becomes_free():
    group = SimpleNamespace(plan_code="pro", plan_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    assert effective_plan(group) == "free"


def test_pro_limits_are_higher():
    group = SimpleNamespace(plan_code="pro", plan_expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    assert plan_limit(group, "words") >= 100
    assert plan_limit(group, "channels") >= 3
