from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_afk_penalties_are_applied_before_winner_checks() -> None:
    source = _source("app/games/mafia/game.py")
    day_block = source.split("elif current == MafiaPhase.DAY_VOTING.value:", 1)[1].split(
        "elif current == MafiaPhase.VOTING_RESULT.value:", 1
    )[0]
    night_block = source.split("elif current == MafiaPhase.NIGHT_ACTIONS.value:", 1)[1].split(
        "elif current == MafiaPhase.NIGHT_RESULT.value:", 1
    )[0]

    for block in (day_block, night_block):
        penalty_pos = block.index("await self._penalize_missing_actions")
        winner_pos = block.index("winning_team = await winner")
        finish_pos = block.index("await finish_game")
        assert penalty_pos < winner_pos < finish_pos


def test_finish_game_is_serialized_and_idempotent() -> None:
    source = _source("app/games/mafia/resolution.py")
    finish_block = source.split("async def finish_game", 1)[1]

    assert ".with_for_update()" in finish_block
    assert "game.status == GameSessionStatus.FINISHED.value" in finish_block
    assert "existing_result = await session.scalar" in finish_block
    assert "if existing_result is None:" in finish_block
    assert 'state.get("result_applied")' in finish_block
    assert "commit=False" in finish_block
    assert finish_block.count("await session.commit()") == 1


def test_finish_game_marks_session_finished_before_applying_stats() -> None:
    source = _source("app/games/mafia/resolution.py")
    finish_block = source.split("async def finish_game", 1)[1]

    status_pos = finish_block.index("game.status = GameSessionStatus.FINISHED.value")
    result_pos = finish_block.index("existing_result = await session.scalar")
    stats_pos = finish_block.index("await apply_game_result")
    commit_pos = finish_block.index("await session.commit()")
    assert status_pos < result_pos < stats_pos < commit_pos
