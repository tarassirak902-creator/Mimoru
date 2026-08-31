from pathlib import Path


HANDLERS = Path("app/games/mafia/handlers.py").read_text(encoding="utf-8")
ACTIONS = Path("app/games/actions.py").read_text(encoding="utf-8")
MODELS = Path("app/db/game_models.py").read_text(encoding="utf-8")


def test_commissioner_result_is_returned_for_repeated_action() -> None:
    assert "async def _commissioner_result" in HANDLERS
    assert 'if player is not None and player.role == "commissioner":' in HANDLERS
    assert "action.target_telegram_id" in HANDLERS
    assert "if created and player is not None and player.role == \"commissioner\"" not in HANDLERS


def test_repeated_action_does_not_create_second_action() -> None:
    assert "if existing is not None:\n        return existing, False" in ACTIONS
    assert 'name="uq_game_action_once_per_phase"' in MODELS


def test_only_new_action_can_advance_phase() -> None:
    marker = "if created:\n        player = await _player"
    assert marker in HANDLERS
    commissioner_block = HANDLERS.index('if player is not None and player.role == "commissioner":')
    created_block = HANDLERS.index(marker, commissioner_block)
    assert commissioner_block < created_block
