from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_words_definition_and_chain_contract() -> None:
    source = read("app/games/words/game.py")
    assert 'code="words"' in source
    assert 'min_players=2' in source
    assert 'max_players=12' in source
    assert 'MAX_STRIKES = 3' in source
    assert 'MAX_ROUNDS = 40' in source
    assert 'used_words' in source
    assert 'required_letter' in source
    assert 'last_letter(' in source
    assert 'apply_game_result(' in source


def test_words_callbacks_are_atomic_and_message_free() -> None:
    game = read("app/games/words/game.py")
    handlers = read("app/games/words/handlers.py")
    keyboard = read("app/games/words/keyboards.py")
    assert '@router.message' not in handlers
    assert '.with_for_update()' in game
    assert 'GameAction.phase_seq == game.phase_seq' in game
    assert 'game.phase_seq != phase_seq' in handlers
    assert 'gm:wo:' in keyboard
    assert 'gm:wp:' in keyboard
    assert 'gm:wskip:' in keyboard
    assert 'callback.answer("\\n".join(lines), show_alert=True)' in handlers


def test_words_timeout_afk_and_recovery_contract() -> None:
    source = read("app/games/words/game.py")
    assert 'async def handle_timeout' in source
    assert 'actor.afk_count += 1' in source
    assert 'if strikes >= MAX_STRIKES:' in source
    assert 'actor.status = "eliminated"' in source
    assert 'async def restore' in source
    assert 'game.phase == "recovering"' in source


def test_words_registry_lobby_and_router_contract() -> None:
    registry = read("app/games/__init__.py")
    lobby = read("app/games/lobby.py")
    wiring = read("app/handlers/fun_preferences.py")
    assert 'from app.games.words import WordsGame, words_definition' in registry
    assert 'game_registry.register(words_definition, WordsGame())' in registry
    assert '"words"' in lobby.split("_TIMED_LOBBY_GAMES", 1)[1].split("}", 1)[0]
    assert 'elif game_type == "words":' in lobby
    assert 'gm:ws:' in lobby
    assert 'words_handlers.router' in wiring
    assert wiring.index('words_handlers.router') < wiring.index('game_handlers.router')
