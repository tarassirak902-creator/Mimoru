from pathlib import Path

from app import tasks_scheduler


ROOT = Path(__file__).resolve().parents[1]


def test_background_tasks_have_separate_cadences() -> None:
    assert tasks_scheduler.FAST_LOOP_SECONDS == 5.0
    assert tasks_scheduler.PERMISSION_TASK_SECONDS >= 30.0
    assert tasks_scheduler.AD_CLEANUP_SECONDS >= 30.0
    assert tasks_scheduler.WARNING_TASK_SECONDS >= 60.0
    assert tasks_scheduler.REPORT_TASK_SECONDS >= 60.0
    assert tasks_scheduler.SUBSCRIPTION_TASK_SECONDS >= 60.0
    assert tasks_scheduler.GROUP_AUTOMATION_SECONDS >= 300.0


def test_leader_uses_cadence_aware_scheduler() -> None:
    source = (ROOT / "app/services/background_leader.py").read_text(encoding="utf-8")
    assert "from app.tasks_scheduler import background_loop" in source
    assert "from app.tasks_delivery import background_loop" not in source
