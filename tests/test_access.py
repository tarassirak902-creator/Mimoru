from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services.plans import effective_plan, plan_limit

ROOT = Path(__file__).resolve().parents[1]


def test_trial_plan_limits():
    group = SimpleNamespace(plan_code="trial", plan_expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    assert effective_plan(group) == "trial"
    assert plan_limit(group, "channels") == 5


def test_expired_plan_falls_back_to_free():
    group = SimpleNamespace(plan_code="pro", plan_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    assert effective_plan(group) == "free"
    assert plan_limit(group, "words") == 10


def test_telegram_admin_lookup_fails_closed_on_api_errors():
    source = (ROOT / "app/services/access.py").read_text(encoding="utf-8")
    function = source.split("async def is_telegram_admin", 1)[1].split("async def is_group_owner", 1)[0]
    assert "TelegramBadRequest" in function
    assert "TelegramForbiddenError" in function
    assert "return False" in function
