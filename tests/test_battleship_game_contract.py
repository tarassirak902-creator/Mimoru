from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_battleship_definition_is_two_player_duel() -> None:
    source = (ROOT / "app/games/battleship/game.py").read_text(encoding="utf-8")
    assert 'code="battleship"' in source
    assert "min_players=2" in source
    assert "max_players=2" in source
    assert "exclusive_group_game=False" in source
    assert "BOARD_SIZE = 5" in source


def test_battleship_turns_are_phase_scoped_and_locked() -> None:
    source = (ROOT / "app/games/battleship/game.py").read_text(encoding="utf-8")
    assert ".with_for_update()" in source
    assert 'GameAction.action_type == "battleship_fire"' in source
    assert "game.phase_seq += 1" in source
    assert "cell already fired" in source
    assert "not your turn" in source


def test_battleship_timeout_and_recovery_are_durable() -> None:
    source = (ROOT / "app/games/battleship/game.py").read_text(encoding="utf-8")
    assert "async def handle_timeout" in source
    assert "current_player.afk_count += 1" in source
    assert 'if game.phase == "recovering":' in source
    assert "state.get(\"boards\")" in source
    assert "game.deadline_at is None" in source


def test_battleship_private_board_is_callback_only() -> None:
    handlers = (ROOT / "app/games/battleship/handlers.py").read_text(encoding="utf-8")
    presentation = (ROOT / "app/games/battleship/presentation.py").read_text(encoding="utf-8")
    assert "@router.message" not in handlers
    assert 'r"^gm:bm:\\d+:\\d+$"' in handlers
    assert "await callback.answer(text[:200], show_alert=True)" in handlers
    assert "battleship_private_board_text" in presentation


def test_battleship_is_registered_and_routed_before_generic_games() -> None:
    registry = (ROOT / "app/games/__init__.py").read_text(encoding="utf-8")
    routing = (ROOT / "app/handlers/fun_preferences.py").read_text(encoding="utf-8")
    lobby = (ROOT / "app/games/lobby.py").read_text(encoding="utf-8")
    assert "BattleshipGame, battleship_definition" in registry
    assert "game_registry.register(battleship_definition, BattleshipGame())" in registry
    specific = "router.include_router(battleship_handlers.router)"
    generic = "router.include_router(game_handlers.router)"
    assert routing.index(specific) < routing.index(generic)
    assert 'elif game_type == "battleship":' in lobby
    assert 'start_callback = f"gm:bs:{game_id}"' in lobby
    assert '"battleship"' in lobby.split("_TIMED_LOBBY_GAMES", 1)[1]


def test_battleship_reuses_phase_message_and_statistics() -> None:
    presentation = (ROOT / "app/games/battleship/presentation.py").read_text(encoding="utf-8")
    game = (ROOT / "app/games/battleship/game.py").read_text(encoding="utf-8")
    assert "upsert_phase_message(" in presentation
    assert 'kind="phase"' in presentation
    assert "ensure_game_panel(" in presentation
    assert "apply_game_result(" in game
    assert "GameResult(" in game
