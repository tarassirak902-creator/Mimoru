from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_game_recovery_is_durable_and_serialized() -> None:
    source = (ROOT / "app/games/recovery.py").read_text(encoding="utf-8")

    assert "GameSessionStatus.RUNNING.value" in source
    assert "GameSessionStatus.RECOVERING.value" in source
    assert ".with_for_update()" in source
    assert 'game.phase in {"starting", "recovering"}' in source
    assert "await entry.engine.start(session, game)" in source
    assert "await entry.engine.restore(session, game)" in source
    assert "await session.rollback()" in source
    assert "game.status = GameSessionStatus.RECOVERING.value" in source
    assert 'game.finish_reason = "missing_game_engine"' in source
    assert '_sync_engine_ui(bot, entry.engine, session, game)' in source
    assert '"game_start_recovered"' in source
    assert '"game_recovered"' in source
    assert '"game_recovery_failed"' in source


def test_failed_recovery_rolls_back_before_marking_recovering() -> None:
    source = (ROOT / "app/games/recovery.py").read_text(encoding="utf-8")
    recovery = source.split("async def recover_active_games", 1)[1].split(
        "async def process_game_timeouts", 1
    )[0]

    rollback = recovery.index("await session.rollback()")
    refetch = recovery.index("select(GameSession).where(GameSession.id == game_id).with_for_update()", rollback)
    mark = recovery.index("game.status = GameSessionStatus.RECOVERING.value", refetch)
    commit = recovery.index("await session.commit()", mark)
    assert rollback < refetch < mark < commit


def test_game_timeouts_revalidate_deadline_under_lock() -> None:
    source = (ROOT / "app/games/recovery.py").read_text(encoding="utf-8")
    timeout = source.split("async def process_game_timeouts(bot: Bot | None = None)", 1)[1]

    assert "GameSession.deadline_at <= now" in timeout
    assert ".limit(100)" in timeout
    assert ".with_for_update()" in timeout
    assert "game.deadline_at > datetime.now(timezone.utc)" in timeout
    assert "entry.engine.handle_timeout(session, game)" in timeout
    assert "expected_phase_seq = game.phase_seq" in timeout
    assert '"game_lobby_timeout"' in timeout
    assert '"game_timeout_processed"' in timeout
    assert '"game_timeout_failed"' in timeout


def test_game_jobs_use_existing_leader_scheduler() -> None:
    scheduler = (ROOT / "app/tasks_scheduler.py").read_text(encoding="utf-8")

    assert "from app.games.recovery import process_game_timeouts, recover_active_games" in scheduler
    assert 'await _run_job("recover_active_games", lambda: recover_active_games(bot))' in scheduler
    assert 'await _run_job("process_game_timeouts", lambda: process_game_timeouts(bot))' in scheduler
    assert scheduler.count("while not stop_event.is_set()") == 1