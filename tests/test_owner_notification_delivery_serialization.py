from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_owner_delivery_locks_group_before_resolving_recipient_and_sending() -> None:
    source = (ROOT / "app/services/owner_notifications.py").read_text(encoding="utf-8")
    body = source.split("async def send_to_current_group_owner", 1)[1]

    group_lock = body.index("select(Group).where(Group.id == group_id).with_for_update()")
    owner = body.index("owner_id = group.owner_telegram_id")
    send = body.index("await bot.send_message(owner_id, text)")
    commit = body.index("await session.commit()", send)

    assert group_lock < owner < send < commit
    assert "group.owner_telegram_id is None" in body
    assert "not group.is_active" in body


def test_daily_report_claim_precedes_current_owner_delivery() -> None:
    source = (ROOT / "app/tasks_delivery.py").read_text(encoding="utf-8")
    start = source.index("async def send_daily_reports")
    end = source.index("async def _claim_subscription_notice", start)
    body = source[start:end]

    claim = body.index("await _claim_daily_report(")
    delivery = body.index("await send_to_current_group_owner(")
    assert claim < delivery
    assert "bot.send_message(\n                    group.owner_telegram_id" not in body


def test_daily_report_claim_revalidates_current_group_before_ledger_update() -> None:
    source = (ROOT / "app/tasks_delivery.py").read_text(encoding="utf-8")
    start = source.index("async def _claim_daily_report")
    end = source.index("async def send_daily_reports", start)
    body = source[start:end]

    lock = body.index("select(Group).where(Group.id == group_id).with_for_update()")
    enabled = body.index("not settings.reports_enabled")
    entitlement = body.index('not feature_available(locked_group, "daily_reports")')
    ledger = body.index("update(GroupSettings)")
    commit = body.index("await session.commit()")
    assert lock < enabled < entitlement < ledger < commit


def test_subscription_claim_precedes_current_owner_delivery() -> None:
    source = (ROOT / "app/tasks_delivery.py").read_text(encoding="utf-8")
    start = source.index("async def send_subscription_notices")
    end = source.index("async def recover_interrupted_scheduled_messages", start)
    body = source[start:end]

    claim = body.index("await _claim_subscription_notice(group.id, event_type, expires_at)")
    delivery = body.index("await send_to_current_group_owner(")
    assert claim < delivery
    assert "bot.send_message(\n                    group.owner_telegram_id" not in body


def test_subscription_claim_uses_locked_current_owner_for_ledger() -> None:
    source = (ROOT / "app/tasks_delivery.py").read_text(encoding="utf-8")
    start = source.index("async def _claim_subscription_notice")
    end = source.index("async def send_subscription_notices", start)
    body = source[start:end]

    lock = body.index("select(Group).where(Group.id == group_id).with_for_update()")
    active_check = body.index("not locked_group.is_active")
    owner_check = body.index("locked_group.owner_telegram_id is None")
    expiry_check = body.index("locked_group.plan_expires_at != expected_expires_at")
    actor = body.index("actor_telegram_id=locked_group.owner_telegram_id")
    commit = body.index("await session.commit()")
    assert lock < active_check < owner_check < expiry_check < actor < commit


def test_owner_notification_worker_imports_hardened_delivery_boundary() -> None:
    source = (ROOT / "app/tasks_delivery.py").read_text(encoding="utf-8")
    assert "from app.services.owner_notifications import send_to_current_group_owner" in source
    assert source.count("await send_to_current_group_owner(") == 2
