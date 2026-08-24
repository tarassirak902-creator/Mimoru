from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _billing() -> str:
    return (ROOT / "app/handlers/billing.py").read_text(encoding="utf-8")


def test_precheckout_revalidates_current_active_group_owner() -> None:
    source = _billing()
    pre = source.split("async def pre_checkout", 1)[1].split(
        "async def _locked_global_post", 1
    )[0]
    assert "await _current_owned_group(session, group_id, query.from_user.id)" in pre
    assert "Group.owner_telegram_id == owner_id" in source
    assert "Group.is_active.is_(True)" in source
    assert "Группа больше не активна или уже не принадлежит вам" in pre


def test_post_charge_owner_mismatch_refunds_instead_of_mutating_group() -> None:
    source = _billing()
    handler = source.split("async def successful_payment", 1)[1]
    subscription = handler.split('if len(parts) == 4 and parts[0] == "payment":', 1)[1]
    mismatch = subscription.split(
        "if group.owner_telegram_id != message.from_user.id or not group.is_active:", 1
    )[1].split("start = group.plan_expires_at", 1)[0]
    assert "await _refund_stale_subscription_payment(" in mismatch
    assert "group.plan_code =" not in mismatch
    assert "group.plan_expires_at =" not in mismatch


def test_refund_is_durable_and_retryable() -> None:
    source = _billing()
    refund = source.split("async def _refund_stale_subscription_payment", 1)[1].split(
        "@router.message", 1
    )[0]
    finish = source.split("async def _finish_subscription_refund", 1)[1].split(
        "async def _refund_stale_subscription_payment", 1
    )[0]
    handler = source.split("async def successful_payment", 1)[1]
    pending = handler.split('if payment.status == "refund_pending":', 1)[1].split(
        'if (\n            payment.status != "pending"', 1
    )[0]
    assert 'payment.status = "refund_pending"' in refund
    assert "payment.provider_payment_id = charge_id" in refund
    assert "await _commit_payment_once(" in refund
    assert "await message.bot.refund_star_payment(" in finish
    assert 'payment.status = "refunded"' in finish
    assert "if payment.provider_payment_id == charge_id:" in pending
    assert "await _finish_subscription_refund(" in pending
    assert "record_and_attempt_subscription_duplicate_refund" in pending
