from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_subscription_duplicate_refund_schema_is_created() -> None:
    model = (ROOT / "app/db/payment_refund_models.py").read_text(encoding="utf-8")
    schema = (ROOT / "app/services/ad_market_schema.py").read_text(encoding="utf-8")
    assert "class SubscriptionDuplicateRefund" in model
    assert 'telegram_payment_charge_id: Mapped[str] = mapped_column(String(255), unique=True' in model
    assert "SubscriptionDuplicateRefund.__table__" in schema


def test_duplicate_refund_claim_is_durable_before_telegram_side_effect() -> None:
    source = (ROOT / "app/services/subscription_duplicate_refunds.py").read_text(encoding="utf-8")
    ensure = source.split("async def ensure_subscription_duplicate_refund", 1)[1].split(
        "async def attempt_subscription_duplicate_refund", 1
    )[0]
    live = source.split("async def record_and_attempt_subscription_duplicate_refund", 1)[1].split(
        "async def recover_pending_subscription_duplicate_refunds", 1
    )[0]
    attempt = source.split("async def attempt_subscription_duplicate_refund", 1)[1].split(
        "async def record_and_attempt_subscription_duplicate_refund", 1
    )[0]

    assert 'status="pending"' in ensure
    assert "await session.commit()" in ensure
    assert live.index("await ensure_subscription_duplicate_refund(") < live.index(
        "await attempt_subscription_duplicate_refund(bot, session, refund_id)"
    )
    assert ".with_for_update()" in attempt
    assert attempt.index(".with_for_update()") < attempt.index("refund_star_payment")


def test_duplicate_refund_recovery_is_idempotent_and_retryable() -> None:
    source = (ROOT / "app/services/subscription_duplicate_refunds.py").read_text(encoding="utf-8")
    attempt = source.split("async def attempt_subscription_duplicate_refund", 1)[1].split(
        "async def record_and_attempt_subscription_duplicate_refund", 1
    )[0]

    assert 'if row.status == "refunded":' in attempt
    assert "_already_refunded(error)" in attempt
    assert 'row.status = "refunded"' in attempt
    failed = attempt.split("if not _already_refunded(error):", 1)[1].split(
        'row.status = "refunded"', 1
    )[0]
    assert "row.last_error =" in failed
    assert "await session.commit()" in failed
    assert 'row.status = "pending"' not in failed


def test_terminal_subscription_charge_is_validated_before_duplicate_refund() -> None:
    billing = (ROOT / "app/handlers/billing.py").read_text(encoding="utf-8")
    subscription = billing.split('if len(parts) == 4 and parts[0] == "payment":', 1)[1]
    terminal = subscription.split('if payment.status in {"paid", "refunded"}:', 1)[1].split(
        'if payment.status == "refund_pending":', 1
    )[0]

    for check in (
        "payment.user_telegram_id != message.from_user.id",
        "payment.group_id != group_id",
        "payment.plan_code != parts[3]",
        "successful.currency != payment.currency",
        "successful.total_amount != payment.amount",
    ):
        assert check in terminal
    assert terminal.index("successful.total_amount != payment.amount") < terminal.index(
        "record_and_attempt_subscription_duplicate_refund"
    )


def test_subscription_refund_leader_tick_recovers_both_refund_kinds() -> None:
    leader = (ROOT / "app/services/background_leader.py").read_text(encoding="utf-8")
    periodic = leader.split("async def _recover_subscription_refunds_periodically", 1)[1].split(
        "async def _run_leader_worker", 1
    )[0]
    assert "recover_pending_subscription_refunds" in periodic
    assert "recover_pending_subscription_duplicate_refunds" in periodic
    assert periodic.index("recover_pending_subscription_refunds(bot)") < periodic.index(
        "recover_pending_subscription_duplicate_refunds(bot)"
    )
