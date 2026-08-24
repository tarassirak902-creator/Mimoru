from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_hardened_scheduler_uses_retryable_deleted_cleanup():
    source = (ROOT / "app/tasks_delivery.py").read_text(encoding="utf-8")
    assert "from app.tasks_deleted_cleanup import run_group_automation" in source
    assert "from app.tasks import" not in source


def test_partial_cleanup_schedules_retry_without_advancing_regular_window():
    source = (ROOT / "app/tasks_deleted_cleanup.py").read_text(encoding="utf-8")
    partial = source.split("if cleanup.failed > 0:", 1)[1].split("else:", 1)[0]
    assert "_schedule_retry" in partial
    assert 'status="partial"' in partial
    assert "deleted_cleanup_last_run_at" not in partial


def test_successful_cleanup_advances_regular_window_and_clears_retry():
    source = (ROOT / "app/tasks_deleted_cleanup.py").read_text(encoding="utf-8")
    success = source.split("if cleanup.failed > 0:", 1)[1].split("else:", 1)[1].split(
        "except (TelegramBadRequest", 1
    )[0]
    assert "settings.deleted_cleanup_last_run_at = now" in success
    assert "await session.delete(retry)" in success
    assert 'status="ok"' in success


def test_retry_is_bounded_and_not_a_scheduler_hot_loop():
    source = (ROOT / "app/tasks_deleted_cleanup.py").read_text(encoding="utf-8")
    assert "MAX_RETRY_DELAY = timedelta(hours=24)" in source
    assert "if retry.retry_at > now:" in source
    assert "continue" in source.split("if retry.retry_at > now:", 1)[1].split("else:", 1)[0]
    assert "2 ** max(0, attempts - 1)" in source


def test_retry_ledger_has_one_row_per_group():
    model = (ROOT / "app/db/deleted_cleanup_retry_models.py").read_text(encoding="utf-8")
    migration = (ROOT / "alembic/versions/0043_deleted_cleanup_retries.py").read_text(encoding="utf-8")
    assert 'primary_key=True' in model
    assert '"deleted_cleanup_retries"' in migration
    assert 'sa.ForeignKey("groups.id", ondelete="CASCADE")' in migration
