from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_roulette_definition_and_fixed_drum_contract() -> None:
    source = (ROOT / "app/games/roulette/game.py").read_text(encoding="utf-8")

    assert 'code="roulette"' in source
    assert 'title="💣 Рулетка"' in source
    assert "min_players=2" in source
    assert "max_players=12" in source
    assert "CHAMBERS = 6" in source
    assert 'return {"bullet": rng.randrange(CHAMBERS), "chamber": 0}' in source
    assert 'drum = dict(state.get("drum") or {})' in source
    assert "fired = chamber == bullet" in source


def test_roulette_turn_is_locked_and_once_per_phase() -> None:
    source = (ROOT / "app/games/roulette/game.py").read_text(encoding="utf-8")
    block = source.split("async def trigger", 1)[1].split("async def handle_timeout", 1)[0]

    assert ".with_for_update()" in block
    assert 'actor_telegram_id != state.get("turn_user_id")' in block
    assert 'GameAction.action_type == "roulette_trigger"' in block
    assert 'action_type="roulette_trigger"' in block
    assert "game.phase_seq += 1" in block
    assert "cell" not in block


def test_roulette_timeout_uses_same_atomic_trigger_path() -> None:
    source = (ROOT / "app/games/roulette/game.py").read_text(encoding="utf-8")
    block = source.split("async def handle_timeout", 1)[1].split("async def restore", 1)[0]

    assert "player.afk_count += 1" in block
    assert "await session.flush()" in block
    assert "await self.trigger(session, game, actor_telegram_id=current)" in block
    assert "await session.commit()" not in block


def test_roulette_recovery_and_durable_result_contract() -> None:
    source = (ROOT / "app/games/roulette/game.py").read_text(encoding="utf-8")

    assert 'if game.phase == "recovering":' in source
    assert 'state.get("alive_user_ids")' in source
    assert 'state.get("drum")' in source
    assert "GameResult(" in source
    assert 'winner_type="player"' in source
    assert "await apply_game_result(" in source
    assert 'player_state' not in source or 'result_applied' in source


def test_roulette_is_registered_and_router_precedes_generic() -> None:
    registry = (ROOT / "app/games/__init__.py").read_text(encoding="utf-8")
    routing = (ROOT / "app/handlers/fun_preferences.py").read_text(encoding="utf-8")
    lobby = (ROOT / "app/games/lobby.py").read_text(encoding="utf-8")

    assert "from app.games.roulette import RouletteGame, roulette_definition" in registry
    assert "game_registry.register(roulette_definition, RouletteGame())" in registry
    roulette = "router.include_router(roulette_handlers.router)"
    generic = "router.include_router(game_handlers.router)"
    assert roulette in routing and generic in routing
    assert routing.index(roulette) < routing.index(generic)
    assert 'elif game_type == "roulette":' in lobby
    assert 'start_callback = f"gm:rs:{game_id}"' in lobby
    assert '"roulette"' in lobby.split("_TIMED_LOBBY_GAMES", 1)[1]


def test_roulette_uses_callbacks_and_reuses_phase_message() -> None:
    handlers = (ROOT / "app/games/roulette/handlers.py").read_text(encoding="utf-8")
    presentation = (ROOT / "app/games/roulette/presentation.py").read_text(encoding="utf-8")
    keyboards = (ROOT / "app/games/roulette/keyboards.py").read_text(encoding="utf-8")

    assert "@router.message" not in handlers
    assert "@router.callback_query" in handlers
    assert 'callback_data=f"gm:rt:{game_id}:{phase_seq}"' in keyboards
    assert "bullet" not in keyboards
    assert "upsert_phase_message(" in presentation
    assert 'kind="phase"' in presentation
    assert "ensure_game_panel(" in presentation
    assert "bot.send_message" not in presentation
