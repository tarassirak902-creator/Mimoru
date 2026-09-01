from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_arena_definition_and_combat_contract():
    source = read("app/games/arena/game.py")
    assert 'code="arena"' in source
    assert 'min_players=2' in source and 'max_players=8' in source
    assert 'START_HP = 5' in source
    assert '"attack", "guard", "heal"' in source
    assert '.with_for_update()' in source
    assert 'GameAction.phase_seq == game.phase_seq' in source
    assert 'apply_game_result(' in source


def test_arena_timeout_is_atomic_and_recovery_safe():
    game = read("app/games/arena/game.py")
    timeout = game.split("async def handle_timeout", 1)[1].split("async def restore", 1)[0]

    assert 'action_type="arena_timeout_guard"' in timeout
    assert 'actor.afk_count += 1' in timeout
    assert 'actor_state["guard"] = True' in timeout
    assert 'game.phase_seq += 1' in timeout
    assert 'game.deadline_at = datetime.now(timezone.utc)' in timeout
    assert 'await self.act(' not in timeout
    assert timeout.count("await session.commit()") == 1


def test_arena_recovery_and_ui_contract():
    game = read("app/games/arena/game.py")
    handlers = read("app/games/arena/handlers.py")
    keyboard = read("app/games/arena/keyboards.py")
    assert 'async def restore' in game
    assert 'game.phase_seq != seq' in handlers
    assert 'gm:aa:' in keyboard and 'gm:ag:' in keyboard and 'gm:ah:' in keyboard
    assert '@router.message' not in handlers


def test_arena_wiring_contract():
    registry = read("app/games/__init__.py")
    lobby = read("app/games/lobby.py")
    wiring = read("app/handlers/fun_preferences.py")
    assert 'ArenaGame, arena_definition' in registry
    assert 'game_registry.register(arena_definition, ArenaGame())' in registry
    assert 'elif game_type == "arena":' in lobby
    assert 'gm:as:' in lobby
    assert 'arena_handlers.router' in wiring
