from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.handlers.required_direct import ActivationError, activate_deal_subscription


ROOT = Path(__file__).resolve().parents[1]


def _atomic_source() -> str:
    return (ROOT / "app/handlers/ad_market_atomic.py").read_text(encoding="utf-8")


def test_deal_decision_autoactivates_on_accept() -> None:
    source = _atomic_source()
    assert "activate_deal_subscription(" in source
    assert "activation_ok" in source
    assert "ActivationError" in source


def test_deal_decision_sends_buyer_activation_status() -> None:
    source = _atomic_source()
    assert "Обязательная подписка уже активна" in source
    assert "Продавец должен включить ОП вручную" in source


def test_deal_decision_seller_sees_activation_result() -> None:
    source = _atomic_source()
    assert "автоматически включена на" in source
    assert "Автоматическая активация не удалась" in source


def test_activate_deal_subscription_exists() -> None:
    source = (ROOT / "app/handlers/required_direct.py").read_text(encoding="utf-8")
    assert "async def activate_deal_subscription(" in source
    assert "class ActivationError" in source


def test_activate_deal_subscription_checks_limit() -> None:
    source = (ROOT / "app/handlers/required_direct.py").read_text(encoding="utf-8")
    assert "active_count >= plan_limit" in source
    assert "plan_limit(group" in source


def test_hardcoded_limit_removed() -> None:
    source = (ROOT / "app/handlers/required_direct.py").read_text(encoding="utf-8")
    assert '— 5.' not in source
