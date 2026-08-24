from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_live_stale_subscription_claim_is_committed_before_refund() -> None:
    billing = (ROOT / "app/handlers/billing.py").read_text(encoding="utf-8")
    helper = billing.split("async def _refund_stale_subscription_payment", 1)[1].split(
        "@router.message(F.successful_payment)", 1
    )[0]

    assert 'payment.status = "refund_pending"' in helper
    assert "payment.provider_payment_id = charge_id" in helper
    assert helper.index("await _commit_payment_once(") < helper.index(
        "await _finish_subscription_refund("
    )


def test_recovery_locks_payment_before_refund_side_effect() -> None:
    source = (ROOT / "app/services/subscription_refunds.py").read_text(encoding="utf-8")
    retry = source.split("async def retry_pending_subscription_refund", 1)[1].split(
        "async def recover_pending_subscription_refunds", 1
    )[0]

    assert ".with_for_update()" in retry
    assert 'payment.status != "refund_pending"' in retry
    assert "charge_id = payment.provider_payment_id" in retry
    assert "if not charge_id:" in retry
    assert retry.index(".with_for_update()") < retry.index("refund_star_payment")


def test_recovery_is_idempotent_and_preserves_pending_on_transient_failure() -> None:
    source = (ROOT / "app/services/subscription_refunds.py").read_text(encoding="utf-8")
    retry = source.split("async def retry_pending_subscription_refund", 1)[1].split(
        "async def recover_pending_subscription_refunds", 1
    )[0]

    assert 'if payment.status == "refunded":' in retry
    assert "_already_refunded(error)" in retry
    assert 'payment.status = "refunded"' in retry
    failed = retry.split("if not _already_refunded(error):", 1)[1].split(
        'payment.status = "refunded"', 1
    )[0]
    assert "return False" in failed
    assert 'payment.status = "refund_pending"' not in failed


def test_recovery_scans_only_pending_rows_in_bounded_batches() -> None:
    source = (ROOT / "app/services/subscription_refunds.py").read_text(encoding="utf-8")
    recovery = source.split("async def recover_pending_subscription_refunds", 1)[1]

    assert 'Payment.status == "refund_pending"' in recovery
    assert ".limit(limit)" in recovery
    assert "await retry_pending_subscription_refund(bot, session, payment_id)" in recovery


def test_subscription_refund_recovery_runs_only_inside_leader_worker() -> None:
    leader = (ROOT / "app/services/background_leader.py").read_text(encoding="utf-8")
    assert "recover_pending_subscription_refunds" in leader
    assert "_recover_subscription_refunds_periodically" in leader
    assert 'name="subscription-refund-recovery"' in leader

    worker = leader.split("async def _run_leader_worker", 1)[1].split(
        "async def leader_background_loop", 1
    )[0]
    assert "subscription_refund_recovery = asyncio.create_task(" in worker
    assert "await stop_task(subscription_refund_recovery, timeout=2.0)" in worker
