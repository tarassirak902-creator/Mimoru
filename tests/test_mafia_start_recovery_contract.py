from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mafia_restore_restarts_interrupted_initialization() -> None:
    source = (ROOT / "app/games/mafia/game.py").read_text(encoding="utf-8")
    restore = source.split("async def restore(", 1)[1].split("async def sync_ui(", 1)[0]

    assert 'game.phase in {"starting", "recovering"}' in restore
    assert "game.status = GameSessionStatus.RUNNING.value" in restore
    assert "await self.start(session, game)" in restore
    assert '"mafia_start_recovered"' in restore


def test_mafia_restore_rejects_unknown_active_phase() -> None:
    source = (ROOT / "app/games/mafia/game.py").read_text(encoding="utf-8")
    restore = source.split("async def restore(", 1)[1].split("async def sync_ui(", 1)[0]

    assert "RECOVERABLE_MAFIA_PHASES" in source
    assert "if game.phase not in RECOVERABLE_MAFIA_PHASES" in restore
    assert "invalid mafia recovery phase" in restore


def test_mafia_normal_recovery_keeps_existing_deadline_or_recreates_one() -> None:
    source = (ROOT / "app/games/mafia/game.py").read_text(encoding="utf-8")
    restore = source.split("async def restore(", 1)[1].split("async def sync_ui(", 1)[0]

    assert "if game.deadline_at is None" in restore
    assert "self.definition.default_timeout_seconds" in restore
    assert '"mafia_restored"' in restore
