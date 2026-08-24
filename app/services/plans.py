from __future__ import annotations

from datetime import datetime, timezone
from math import ceil

# Moderator/administrator count is intentionally not tariff-gated. Telegram
# administrators and Mimoru roles are an operational permission model, not a
# commercial limit. Required-subscription slots are also the same for every
# plan: a group may configure at most five channels.
PLAN_CATALOG = {
    "free": {
        "title": "FREE",
        "stars": 0,
        "days": 0,
        "limits": {"words": 10, "channels": 5, "moderators": 1_000_000, "reasons": 5},
        "features": {"basic_moderation", "basic_protection", "basic_stats"},
    },
    "trial": {
        "title": "TRIAL",
        "stars": 0,
        "days": 0,
        "limits": {"words": 100, "channels": 5, "moderators": 1_000_000, "reasons": 30},
        "features": {
            "basic_moderation", "basic_protection", "basic_stats",
            "advanced_protection", "advanced_analytics", "daily_reports",
        },
    },
    "standard": {
        "title": "STANDARD",
        "stars": 250,
        "days": 30,
        "limits": {"words": 100, "channels": 5, "moderators": 1_000_000, "reasons": 30},
        "features": {
            "basic_moderation", "basic_protection", "basic_stats",
            "advanced_protection", "advanced_analytics", "daily_reports", "ads_marketplace",
        },
    },
    "pro": {
        "title": "PRO",
        "stars": 500,
        "days": 30,
        "limits": {"words": 1000, "channels": 5, "moderators": 1_000_000, "reasons": 100},
        "features": {
            "basic_moderation", "basic_protection", "basic_stats",
            "advanced_protection", "advanced_analytics", "daily_reports",
            "ads_marketplace", "priority_support", "max_limits",
        },
    },
}

# Compatibility for older imports/tests.
PLAN_LIMITS = {code: data["limits"] for code, data in PLAN_CATALOG.items()}


def effective_plan(group, *, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    expires_at = getattr(group, "plan_expires_at", None)
    if expires_at and expires_at <= now:
        return "free"
    code = (getattr(group, "plan_code", None) or "free").casefold()
    return code if code in PLAN_CATALOG else "free"


def plan_limit(group, feature: str) -> int:
    plan = PLAN_CATALOG[effective_plan(group)]
    if feature not in plan["limits"]:
        raise KeyError(f"Unknown plan limit: {feature}")
    return int(plan["limits"][feature])


def feature_available(group, feature: str) -> bool:
    return feature in PLAN_CATALOG[effective_plan(group)]["features"]


def paid_plan(code: str) -> dict:
    normalized = code.casefold()
    if normalized not in {"standard", "pro"}:
        raise KeyError(f"Unknown paid plan: {code}")
    return PLAN_CATALOG[normalized]


def remaining_days(group, *, now: datetime | None = None) -> int | None:
    expires_at = getattr(group, "plan_expires_at", None)
    if expires_at is None:
        return None
    now = now or datetime.now(timezone.utc)
    seconds = (expires_at - now).total_seconds()
    if seconds <= 0:
        return 0
    return max(1, ceil(seconds / 86400))


def subscription_state(group, *, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    expires_at = getattr(group, "plan_expires_at", None)
    code = (getattr(group, "plan_code", None) or "free").casefold()
    if code == "free":
        return "free"
    if expires_at is not None and expires_at <= now:
        return "expired"
    if code == "trial":
        return "trial"
    return "active"
