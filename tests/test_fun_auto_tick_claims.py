from pathlib import Path


SOURCE = Path("app/tasks_fun.py").read_text(encoding="utf-8")


def test_auto_tick_claim_system_is_removed() -> None:
    assert "_claim_auto_tick" not in SOURCE
    assert "_run_claimed_auto_activity" not in SOURCE
    assert "AUTO_TICK_ACTION" not in SOURCE
    assert "MAX_GROUPS_PER_TICK" not in SOURCE


def test_retired_worker_is_explicit_noop() -> None:
    assert "async def run_fun_auto_activity" in SOURCE
    assert "return None" in SOURCE
    assert "async def fun_background_loop" in SOURCE
    assert "await stop_event.wait()" in SOURCE


def test_retired_worker_cannot_send_or_persist_actions() -> None:
    assert "bot.send_message" not in SOURCE
    assert "session.commit" not in SOURCE
    assert "GameEvent" not in SOURCE
