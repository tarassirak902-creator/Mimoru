from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _leader() -> str:
    return (ROOT / "app/services/background_leader.py").read_text(encoding="utf-8")


def test_chat_permission_recovery_has_supervised_periodic_loop() -> None:
    source = _leader()
    periodic = source.split("async def _recover_chat_permissions_periodically", 1)[1].split(
        "async def _recover_rank_provisioning_periodically", 1
    )[0]
    assert "while not local_stop.is_set():" in periodic
    assert "await recover_chat_permission_transitions(bot)" in periodic
    assert 'log.exception("chat_permission_recovery_iteration_failed")' in periodic
    assert "timeout=CHAT_PERMISSION_RECOVERY_SECONDS" in periodic


def test_rank_provisioning_recovery_has_supervised_periodic_loop() -> None:
    source = _leader()
    periodic = source.split("async def _recover_rank_provisioning_periodically", 1)[1].split(
        "async def _recover_join_reviews_periodically", 1
    )[0]
    assert "while not local_stop.is_set():" in periodic
    assert "await recover_rank_provisioning_intents(bot)" in periodic
    assert 'log.exception("rank_provisioning_recovery_iteration_failed")' in periodic
    assert "timeout=RANK_PROVISIONING_RECOVERY_SECONDS" in periodic


def test_leader_starts_and_stops_permission_and_rank_recovery() -> None:
    source = _leader()
    worker = source.split("async def _run_leader_worker", 1)[1].split(
        "async def leader_background_loop", 1
    )[0]

    assert "_recover_chat_permissions_periodically(bot, local_stop)" in worker
    assert 'name="chat-permission-recovery"' in worker
    assert "_recover_rank_provisioning_periodically(bot, local_stop)" in worker
    assert 'name="rank-provisioning-recovery"' in worker
    assert "await stop_task(chat_permission_recovery, timeout=2.0)" in worker
    assert "await stop_task(rank_provisioning_recovery, timeout=2.0)" in worker


def test_existing_startup_recovery_remains_in_main() -> None:
    source = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "await recover_chat_permission_transitions(bot)" in source
    assert "await recover_rank_provisioning_intents(bot)" in source
