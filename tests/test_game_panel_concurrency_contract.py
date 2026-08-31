from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_game_panel_updates_are_serialized_per_group() -> None:
    source = (ROOT / "app/games/panels.py").read_text(encoding="utf-8")
    block = source.split("async def ensure_game_panel", 1)[1].split("async def render_profile", 1)[0]

    lock = 'text("SELECT pg_advisory_lock(:namespace, :group_id)")'
    unlock = 'text("SELECT pg_advisory_unlock(:namespace, :group_id)")'
    assert lock in block
    assert unlock in block
    assert "finally:" in block
    assert block.index(lock) < block.index("await session.get(GamePanel, group.id)")
    assert block.index(lock) < block.index("await bot.send_message")
    assert block.index("finally:") < block.index(unlock)


def test_game_panel_lock_uses_a_dedicated_namespace() -> None:
    source = (ROOT / "app/games/panels.py").read_text(encoding="utf-8")
    assert "_GAME_PANEL_LOCK_NAMESPACE" in source
    assert source.count('"namespace": _GAME_PANEL_LOCK_NAMESPACE') == 2
