from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_detective_definition_and_case_contract() -> None:
    source = read("app/games/detective/game.py")
    assert 'code="detective"' in source
    assert 'min_players=2' in source
    assert 'max_players=20' in source
    assert 'ROUNDS = 4' in source
    assert 'CASE_BANK' in source
    assert '"clues"' in source
    assert '"suspects"' in source
    assert '"correct_index"' in source
    assert 'apply_game_result(' in source


def test_detective_callbacks_hide_answers_until_result() -> None:
    handlers = read("app/games/detective/handlers.py")
    keyboard = read("app/games/detective/keyboards.py")
    presentation = read("app/games/detective/presentation.py")
    assert '@router.message' not in handlers
    assert 'gm:dc:' in keyboard
    assert 'gm:dsus:' in keyboard
    assert 'gm:da:' in keyboard
    assert 'Обвинение принято' in handlers
    assert 'Виновник:' in presentation
    assert 'DetectivePhase.ROUND_RESULT.value' in presentation
    assert 'game.phase_seq != phase_seq' in handlers


def test_detective_atomic_answer_timeout_and_recovery_contract() -> None:
    source = read("app/games/detective/game.py")
    assert '.with_for_update()' in source
    assert 'GameAction.phase_seq == game.phase_seq' in source
    assert 'action_type == "detective_accuse"' in source
    assert 'maybe_advance_if_ready' in source
    assert 'async def handle_timeout' in source
    assert 'async def restore' in source
    assert 'game.phase == "recovering"' in source


def test_detective_registry_lobby_and_router_contract() -> None:
    registry = read("app/games/__init__.py")
    lobby = read("app/games/lobby.py")
    wiring = read("app/handlers/fun_preferences.py")
    assert 'from app.games.detective import DetectiveGame, detective_definition' in registry
    assert 'game_registry.register(detective_definition, DetectiveGame())' in registry
    assert '"detective"' in lobby.split("_TIMED_LOBBY_GAMES", 1)[1].split("}", 1)[0]
    assert 'elif game_type == "detective":' in lobby
    assert 'gm:ds:' in lobby
    assert 'detective_handlers.router' in wiring
    assert wiring.index('detective_handlers.router') < wiring.index('game_handlers.router')
