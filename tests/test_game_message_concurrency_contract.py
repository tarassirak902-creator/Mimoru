from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_game_message_registration_uses_atomic_upsert() -> None:
    source = (ROOT / "app/games/messages.py").read_text(encoding="utf-8")
    block = source.split("async def register_game_message", 1)[1].split("async def retire_game_message", 1)[0]

    assert "from sqlalchemy.dialects.postgresql import insert" in source
    assert "insert(GameMessage)" in block
    assert ".on_conflict_do_update(" in block
    assert 'index_elements=["game_id", "message_id"]' in block


def test_phase_message_side_effects_are_serialized_per_game() -> None:
    source = (ROOT / "app/games/messages.py").read_text(encoding="utf-8")
    block = source.split("async def upsert_phase_message", 1)[1]

    assert "await advisory_xact_lock(" in block
    assert "namespace=_GAME_PHASE_MESSAGE_LOCK_NAMESPACE" in block
    assert block.index("await advisory_xact_lock(") < block.index("select(GameMessage)")
    assert block.index("await advisory_xact_lock(") < block.index("await bot.send_message")
    assert "await session.rollback()" in block


def test_game_advisory_helper_is_transaction_scoped() -> None:
    source = (ROOT / "app/games/locks.py").read_text(encoding="utf-8")
    assert "pg_advisory_xact_lock" in source
    assert "pg_advisory_unlock" not in source
    assert "pg_advisory_lock(" not in source
