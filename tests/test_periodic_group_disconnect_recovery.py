from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _leader() -> str:
    return (ROOT / "app/services/background_leader.py").read_text(encoding="utf-8")


def test_group_disconnect_recovery_has_supervised_periodic_loop() -> None:
    source = _leader()
    periodic = source.split("async def _recover_group_disconnects_periodically", 1)[1].split(
        "async def _recover_join_reviews_periodically", 1
    )[0]
    assert "while not local_stop.is_set():" in periodic
    assert "await recover_group_disconnects(bot)" in periodic
    assert 'log.exception("group_disconnect_recovery_iteration_failed")' in periodic
    assert "timeout=GROUP_DISCONNECT_RECOVERY_SECONDS" in periodic


def test_leader_keeps_initial_recovery_and_starts_periodic_retries() -> None:
    source = _leader()
    worker = source.split("async def _run_leader_worker", 1)[1].split(
        "async def leader_background_loop", 1
    )[0]
    initial = worker.index("await recover_group_disconnects(bot)")
    task = worker.index("disconnect_recovery = asyncio.create_task(")
    scheduled = worker.index("await background_loop(bot, redis, local_stop)")
    assert initial < task < scheduled
    assert "_recover_group_disconnects_periodically(bot, local_stop)" in worker
    assert 'name="group-disconnect-recovery"' in worker


def test_periodic_disconnect_recovery_stops_with_leader_worker() -> None:
    source = _leader()
    worker = source.split("async def _run_leader_worker", 1)[1].split(
        "async def leader_background_loop", 1
    )[0]
    assert "local_stop.set()" in worker
    assert "await stop_task(disconnect_recovery, timeout=2.0)" in worker
