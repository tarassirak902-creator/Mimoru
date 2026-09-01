from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_crocodile_definition_and_registry() -> None:
    game = (ROOT / "app/games/crocodile/game.py").read_text(encoding="utf-8")
    registry = (ROOT / "app/games/__init__.py").read_text(encoding="utf-8")

    assert 'code="crocodile"' in game
    assert "min_players=3" in game
    assert "max_players=20" in game
    assert "uses_private_mapping=True" in game
    assert "CrocodileGame, crocodile_definition" in registry
    assert "game_registry.register(crocodile_definition, CrocodileGame())" in registry


def test_crocodile_starts_only_joined_lobby_players() -> None:
    source = (ROOT / "app/games/crocodile/game.py").read_text(encoding="utf-8")
    start = source.split("async def start", 1)[1].split("async def handle_action", 1)[0]

    assert 'statuses=("joined",)' in start
    assert 'player.status = "alive"' in start
    assert '"host_order": order' in start
    assert '"current_word": words[0]' in start


def test_crocodile_secret_word_is_callback_only() -> None:
    handlers = (ROOT / "app/games/crocodile/handlers.py").read_text(encoding="utf-8")
    presentation = (ROOT / "app/games/crocodile/presentation.py").read_text(encoding="utf-8")

    assert "@router.message" not in handlers
    assert "@router.callback_query" in handlers
    assert 'word = str(state.get("current_word") or "")' in handlers
    assert 'await callback.answer(f"🎭 Ваше слово:' in handlers
    assert 'state.get("current_word")' not in presentation


def test_crocodile_guesser_uses_personal_target_mapping() -> None:
    handlers = (ROOT / "app/games/crocodile/handlers.py").read_text(encoding="utf-8")
    keyboard = (ROOT / "app/games/crocodile/keyboards.py").read_text(encoding="utf-8")

    assert "ensure_target_map(" in handlers
    assert "resolve_target_number(" in handlers
    assert "actor_telegram_id=host_id" in handlers
    assert 'callback_data=f"gm:ct:{game_id}:{phase_seq}:{number}"' in keyboard
    assert 'callback_data=f"gm:cl:{game_id}:{phase_seq}:' in keyboard


def test_crocodile_actions_are_phase_guarded_and_idempotent() -> None:
    game = (ROOT / "app/games/crocodile/game.py").read_text(encoding="utf-8")
    handlers = (ROOT / "app/games/crocodile/handlers.py").read_text(encoding="utf-8")

    assert "GameAction.phase_seq == game.phase_seq" in game
    assert 'GameAction.action_type == "crocodile_guessed"' in game
    assert "game.phase_seq != phase_seq" in handlers
    assert "only current host can confirm guess" in game
    assert "guesser_telegram_id == actor_telegram_id" in game


def test_crocodile_timeout_recovery_and_stats_are_durable() -> None:
    game = (ROOT / "app/games/crocodile/game.py").read_text(encoding="utf-8")

    assert "async def handle_timeout" in game
    assert "host.afk_count += 1" in game
    assert "expected_phase_seq=game.phase_seq" in game
    assert "async def restore" in game
    assert 'game.phase == "recovering"' in game
    assert "GameResult(" in game
    assert "await apply_game_result(" in game
    assert 'state.get("result_applied")' in game


def test_crocodile_reuses_phase_message_and_precedes_generic_router() -> None:
    presentation = (ROOT / "app/games/crocodile/presentation.py").read_text(encoding="utf-8")
    host = (ROOT / "app/handlers/fun_preferences.py").read_text(encoding="utf-8")
    lobby = (ROOT / "app/games/lobby.py").read_text(encoding="utf-8")

    assert "upsert_phase_message(" in presentation
    assert 'kind="phase"' in presentation
    assert "ensure_game_panel(" in presentation
    crocodile = "router.include_router(crocodile_handlers.router)"
    generic = "router.include_router(game_handlers.router)"
    assert crocodile in host and generic in host
    assert host.index(crocodile) < host.index(generic)
    assert 'elif game_type == "crocodile":' in lobby
    assert 'start_callback = f"gm:ccs:{game_id}"' in lobby
    assert '"crocodile"' in lobby.split("_TIMED_LOBBY_GAMES", 1)[1]
