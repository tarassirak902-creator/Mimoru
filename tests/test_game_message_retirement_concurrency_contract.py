from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_game_message_retirement_rechecks_state_under_lock() -> None:
    source = (ROOT / "app/games/messages.py").read_text(encoding="utf-8")
    block = source.split("async def retire_game_message", 1)[1].split(
        "async def retire_active_messages", 1
    )[0]

    lock = "await advisory_xact_lock("
    reload = "select(GameMessage).where(GameMessage.id == record.id).with_for_update()"
    side_effect = "await bot.delete_message"
    assert "_GAME_MESSAGE_RETIRE_LOCK_NAMESPACE" in block
    assert lock in block
    assert reload in block
    assert "current is None or not current.active" in block
    assert block.index(lock) < block.index(reload) < block.index(side_effect)


def test_retirement_does_not_trust_stale_record_active_flag() -> None:
    source = (ROOT / "app/games/messages.py").read_text(encoding="utf-8")
    block = source.split("async def retire_game_message", 1)[1].split(
        "async def retire_active_messages", 1
    )[0]

    assert "if not record.active:" not in block
    assert "current.active = False" in block
    assert "current.retired_at = datetime.now(timezone.utc)" in block
