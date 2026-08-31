from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_game_panel_updates_are_serialized_per_group() -> None:
    source = (ROOT / "app/games/panels.py").read_text(encoding="utf-8")
    block = source.split("async def ensure_game_panel", 1)[1].split("async def render_profile", 1)[0]

    assert "await advisory_xact_lock(" in block
    assert "namespace=_GAME_PANEL_LOCK_NAMESPACE" in block
    assert block.index("await advisory_xact_lock(") < block.index("await session.get(GamePanel, group.id)")
    assert block.index("await advisory_xact_lock(") < block.index("await bot.send_message")
    assert "await session.rollback()" in block


def test_game_panel_does_not_use_session_level_advisory_locks() -> None:
    source = (ROOT / "app/games/panels.py").read_text(encoding="utf-8")
    assert "pg_advisory_lock" not in source
    assert "pg_advisory_unlock" not in source
    assert "_GAME_PANEL_LOCK_NAMESPACE" in source
