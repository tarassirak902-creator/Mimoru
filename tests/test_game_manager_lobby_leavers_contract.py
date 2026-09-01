from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_start_lobby_prunes_players_who_left_before_running() -> None:
    source = (ROOT / "app/games/manager.py").read_text(encoding="utf-8")
    start = source.split("async def start_lobby", 1)[1].split("async def cancel_game", 1)[0]

    assert "from sqlalchemy import delete, select" in source
    assert "players = await self.list_players" in start
    assert 'GamePlayer.status == "left"' in start
    assert "delete(GamePlayer)" in start
    assert start.index("delete(GamePlayer)") < start.index("game.status = GameSessionStatus.RUNNING.value")
    assert start.index("delete(GamePlayer)") < start.index("await session.commit()")


def test_lobby_leaver_can_still_rejoin_before_start() -> None:
    source = (ROOT / "app/games/manager.py").read_text(encoding="utf-8")
    join = source.split("async def join_lobby", 1)[1].split("async def leave_lobby", 1)[0]

    assert 'existing.status = "joined"' in join
    assert "existing.left_at = None" in join
