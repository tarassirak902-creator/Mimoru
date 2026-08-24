from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_refund_pending_same_charge_retries_original_refund() -> None:
    billing = (ROOT / "app/handlers/billing.py").read_text(encoding="utf-8")
    subscription = billing.split('if len(parts) == 4 and parts[0] == "payment":', 1)[1]
    pending_refund = subscription.split('if payment.status == "refund_pending":', 1)[1].split(
        'if (\n            payment.status != "pending"', 1
    )[0]

    same_charge = pending_refund.split("if payment.provider_payment_id == charge_id:", 1)[1].split(
        "if (", 1
    )[0]
    assert "await _finish_subscription_refund(" in same_charge
    assert "charge_id=charge_id" in same_charge
    assert "record_and_attempt_subscription_duplicate_refund" not in same_charge


def test_refund_pending_distinct_charge_uses_durable_duplicate_refund() -> None:
    billing = (ROOT / "app/handlers/billing.py").read_text(encoding="utf-8")
    subscription = billing.split('if len(parts) == 4 and parts[0] == "payment":', 1)[1]
    pending_refund = subscription.split('if payment.status == "refund_pending":', 1)[1].split(
        'if (\n            payment.status != "pending"', 1
    )[0]

    for check in (
        "payment.user_telegram_id != message.from_user.id",
        "payment.group_id != group_id",
        "payment.plan_code != parts[3]",
        "successful.currency != payment.currency",
        "successful.total_amount != payment.amount",
    ):
        assert check in pending_refund
    assert pending_refund.index("successful.total_amount != payment.amount") < pending_refund.index(
        "record_and_attempt_subscription_duplicate_refund"
    )
    assert "payment_id=payment.id" in pending_refund
    assert "buyer_telegram_id=payment.user_telegram_id" in pending_refund
    assert "charge_id=charge_id" in pending_refund


def test_refund_pending_distinct_charge_does_not_replace_original_obligation() -> None:
    billing = (ROOT / "app/handlers/billing.py").read_text(encoding="utf-8")
    subscription = billing.split('if len(parts) == 4 and parts[0] == "payment":', 1)[1]
    pending_refund = subscription.split('if payment.status == "refund_pending":', 1)[1].split(
        'if (\n            payment.status != "pending"', 1
    )[0]

    assert "payment.provider_payment_id = charge_id" not in pending_refund
    assert 'payment.status = "refunded"' not in pending_refund
    assert 'payment.status = "paid"' not in pending_refund
    assert "будет повторён автоматически" in pending_refund
