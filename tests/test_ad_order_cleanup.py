from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_hardened_scheduler_uses_retryable_ad_cleanup():
    source = (ROOT / "app/tasks_delivery.py").read_text(encoding="utf-8")
    assert "from app.tasks_ad_cleanup import complete_ad_orders" in source
    assert "from app.tasks import" not in source


def test_ad_cleanup_claim_is_committed_before_delete_side_effect():
    source = (ROOT / "app/tasks_ad_cleanup.py").read_text(encoding="utf-8")
    claim = source.split("async def _claim_due_order", 1)[1].split("async def _finish_cleanup", 1)[0]
    assert "order.status = CLEANUP_PENDING" in claim
    assert "await session.commit()" in claim
    cleanup = source.split("async def complete_ad_orders", 1)[1]
    assert "await bot.delete_message" in cleanup


def test_retryable_telegram_failures_do_not_finish_cleanup():
    source = (ROOT / "app/tasks_ad_cleanup.py").read_text(encoding="utf-8")
    cleanup = source.split("async def complete_ad_orders", 1)[1]
    forbidden = cleanup.split("except TelegramForbiddenError", 1)[1].split("except TelegramBadRequest", 1)[0]
    assert "continue" in forbidden
    assert "_finish_cleanup" not in forbidden
    bad_request = cleanup.split("except TelegramBadRequest", 1)[1].split("await _finish_cleanup", 1)[0]
    assert "if not _message_definitely_absent(error)" in bad_request
    assert "continue" in bad_request


def test_only_explicit_missing_message_is_terminal_bad_request():
    source = (ROOT / "app/tasks_ad_cleanup.py").read_text(encoding="utf-8")
    helper = source.split("def _message_definitely_absent", 1)[1].split("async def _claim_due_order", 1)[0]
    assert '"message to delete not found" in text' in helper


def test_cleanup_pending_is_restart_retryable():
    source = (ROOT / "app/tasks_ad_cleanup.py").read_text(encoding="utf-8")
    claim = source.split("async def _claim_due_order", 1)[1].split("async def _finish_cleanup", 1)[0]
    assert "if order.status == CLEANUP_PENDING" in claim
    candidates = source.split("candidate_ids =", 1)[1].split("for order_id", 1)[0]
    assert 'AdOrder.status.in_(["published", CLEANUP_PENDING])' in candidates


def test_order_is_completed_only_through_finish_cleanup_after_claim():
    source = (ROOT / "app/tasks_ad_cleanup.py").read_text(encoding="utf-8")
    finish = source.split("async def _finish_cleanup", 1)[1].split("async def complete_ad_orders", 1)[0]
    assert "AdOrder.status == CLEANUP_PENDING" in finish
    assert '.values(status="completed", completed_at=now)' in finish
