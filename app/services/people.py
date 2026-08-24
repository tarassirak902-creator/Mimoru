from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass(frozen=True)
class ReputationResult:
    score: int
    trust: str
    risk: int

def calculate_reputation(*, messages: int, warnings: int, mutes: int, bans: int, complaints: int, days_in_group: int, deleted_messages: int = 0, override: int | None = None) -> ReputationResult:
    if override is not None:
        score = max(0, min(100, int(override)))
    else:
        score = 50
        score += min(20, messages // 100)
        score += min(15, max(0, days_in_group) // 30)
        score -= warnings * 8
        score -= mutes * 12
        score -= bans * 30
        score -= complaints * 3
        score -= min(10, deleted_messages // 20)
        score = max(0, min(100, score))
    if score >= 80 and days_in_group >= 30:
        trust = "trusted"
    elif score < 35:
        trust = "watch"
    elif days_in_group < 7:
        trust = "new"
    else:
        trust = "normal"
    risk = max(0, min(100, 100 - score + (20 if days_in_group < 2 else 0)))
    return ReputationResult(score, trust, risk)

def days_since(value: datetime | None) -> int:
    if value is None:
        return 0
    now = datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return max(0, (now - value).days)

def trust_label(code: str) -> str:
    return {
        "telegram_owner": "👑 Владелец Telegram-группы",
        "telegram_admin": "🛡 Администратор Telegram",
        "trusted": "🟢 Проверенный",
        "normal": "🔵 Обычный",
        "new": "🟡 Новый",
        "watch": "🔴 Под наблюдением",
    }.get(code, "🔵 Обычный")
