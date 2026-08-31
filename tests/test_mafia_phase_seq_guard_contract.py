from pathlib import Path


GAME_PATH = Path("app/games/mafia/game.py")


def test_phase_advance_requires_expected_phase_sequence() -> None:
    source = GAME_PATH.read_text(encoding="utf-8")

    assert "expected_phase_seq: int" in source
    assert "if game.phase_seq != expected_phase_seq:" in source
    assert '"mafia_phase_advance_stale"' in source
    assert "return False" in source


def test_timeout_passes_observed_phase_sequence() -> None:
    source = GAME_PATH.read_text(encoding="utf-8")

    timeout = source.split("async def handle_timeout", 1)[1].split("async def maybe_advance_if_ready", 1)[0]
    assert "expected_phase_seq=game.phase_seq" in timeout


def test_ready_transition_returns_guarded_advance_result() -> None:
    source = GAME_PATH.read_text(encoding="utf-8")

    ready = source.split("async def maybe_advance_if_ready", 1)[1].split("async def restore", 1)[0]
    assert "expected_phase_seq = game.phase_seq" in ready
    assert ready.count("return await self._advance_phase(") == 2
    assert ready.count("expected_phase_seq=expected_phase_seq") == 2
