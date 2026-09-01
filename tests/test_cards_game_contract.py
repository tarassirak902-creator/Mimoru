from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_cards_definition_and_engine_contract() -> None:
    source = _read("app/games/cards/game.py")
    assert 'code="cards"' in source
    assert 'min_players=2' in source
    assert 'max_players=8' in source
    assert 'supports_rating=True' in source
    assert 'statuses=("joined",)' in source
    assert 'GameSessionStatus.FINISHED.value' in source
    assert 'apply_game_result(' in source
    assert 'async def handle_timeout' in source
    assert 'async def restore' in source


def test_cards_secret_hand_and_callback_contract() -> None:
    handlers = _read("app/games/cards/handlers.py")
    keyboard = _read("app/games/cards/keyboards.py")
    presentation = _read("app/games/cards/presentation.py")
    assert '@router.message' not in handlers
    assert 'callback.answer("\\n".join(lines), show_alert=True)' in handlers
    assert 'gm:ch:' in keyboard
    assert 'gm:cp:' in keyboard
    assert 'gm:cd:' in keyboard
    assert 'hands = dict(state.get("hands") or {})' in presentation
    assert 'card_label(top)' in presentation
    assert 'hand' not in keyboard.casefold()


def test_cards_atomic_turn_and_stale_callback_contract() -> None:
    game = _read("app/games/cards/game.py")
    handlers = _read("app/games/cards/handlers.py")
    assert '.with_for_update()' in game
    assert 'GameAction.game_id == game.id' in game
    assert 'GameAction.phase_seq == game.phase_seq' in game
    assert 'game.phase_seq != phase_seq' in handlers
    assert 'прошлому ходу' in handlers
    assert 'not your turn' in game


def test_cards_wiring_contract() -> None:
    registry = _read("app/games/__init__.py")
    lobby = _read("app/games/lobby.py")
    wiring = _read("app/handlers/fun_preferences.py")
    assert 'from app.games.cards import CardsGame, cards_definition' in registry
    assert 'game_registry.register(cards_definition, CardsGame())' in registry
    assert '"cards"' in lobby
    assert 'gm:cgs:' in lobby
    assert 'cards_handlers.router' in wiring
