from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_profile_keyboard_is_compact_two_column_grid() -> None:
    source = (ROOT / "app/handlers/member_profile_v2.py").read_text(encoding="utf-8")
    block = source.split("def _profile_keyboard", 1)[1].split("async def _active_group", 1)[0]

    assert '[button("profile", "👤 Профиль"), button("history", "⚖️ История")]' in block
    assert '[button("games", "🎮 Игры"), button("rp", rp_label)]' in block
    assert '[button("close", "❌ Закрыть")]' in block
    assert '[button("profile", "👤 Профиль")]' not in block
    assert '[button("rp", rp_label)]' not in block
