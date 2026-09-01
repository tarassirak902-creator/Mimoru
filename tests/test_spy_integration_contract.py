from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_spy_is_registered_in_shared_game_registry() -> None:
    source = (ROOT / "app/games/__init__.py").read_text(encoding="utf-8")

    assert "from app.games.spy import SpyGame, spy_definition" in source
    assert "game_registry.get(spy_definition.code)" in source
    assert "game_registry.register(spy_definition, SpyGame())" in source


def test_spy_router_precedes_generic_game_router() -> None:
    source = (ROOT / "app/handlers/fun_preferences.py").read_text(encoding="utf-8")

    assert "from app.games.spy import handlers as spy_handlers" in source
    spy = "router.include_router(spy_handlers.router)"
    generic = "router.include_router(game_handlers.router)"
    assert spy in source and generic in source
    assert source.index(spy) < source.index(generic)


def test_spy_lobby_uses_special_start_and_shared_lobby_message() -> None:
    source = (ROOT / "app/games/lobby.py").read_text(encoding="utf-8")

    assert 'elif game_type == "spy":' in source
    assert 'start_callback = f"gm:ss:{game_id}"' in source
    timed = source.split("_TIMED_LOBBY_GAMES", 1)[1].split("}", 1)[0]
    assert '"spy"' in timed
    assert "game.lobby_message_id" in source
    assert "bot.edit_message_text(" in source


def test_spy_ui_reuses_phase_message_and_main_game_panel() -> None:
    source = (ROOT / "app/games/spy/presentation.py").read_text(encoding="utf-8")

    assert "upsert_phase_message(" in source
    assert 'kind="phase"' in source
    assert "ensure_game_panel(" in source
    assert "pin=False" in source
    assert "bot.send_message" not in source


def test_spy_has_no_plain_message_gameplay_handler() -> None:
    source = (ROOT / "app/games/spy/handlers.py").read_text(encoding="utf-8")

    assert "@router.message" not in source
    assert "@router.callback_query" in source
