from pathlib import Path

import pytest

from app.games.config import GameDefinition
from app.games.registry import GameRegistry


ROOT = Path(__file__).resolve().parents[1]


def test_game_definition_validates_player_limits() -> None:
    game = GameDefinition(code="mafia", title="🐺 Мафия", min_players=4, max_players=15)
    assert game.code == "mafia"
    assert game.exclusive_group_game is True
    assert game.supports_rating is True

    with pytest.raises(ValueError):
        GameDefinition(code="broken", title="x", min_players=5, max_players=4)


def test_game_registry_rejects_duplicate_codes() -> None:
    registry = GameRegistry()
    definition = GameDefinition(code="dummy", title="Dummy", min_players=2, max_players=4)
    registry.register(definition)
    assert registry.require("dummy") is definition
    with pytest.raises(ValueError):
        registry.register(definition)
    with pytest.raises(KeyError):
        registry.require("missing")


def test_game_schema_enforces_one_active_game_per_group() -> None:
    migration = (ROOT / "alembic/versions/0046_game_engine_core.py").read_text(encoding="utf-8")
    assert 'down_revision = "0045_moderation_command_modes"' in migration
    assert '"uq_game_sessions_one_active_per_group"' in migration
    assert "status IN ('lobby','running','recovering')" in migration
    assert '"uq_game_action_once_per_phase"' in migration
    assert '"uq_game_target_map_number"' in migration
    assert '"uq_game_target_map_target"' in migration


def test_game_manager_serializes_lobby_creation_and_mutations() -> None:
    source = (ROOT / "app/games/manager.py").read_text(encoding="utf-8")
    create = source.split("async def create_lobby(", 1)[1].split("async def join_lobby(", 1)[0]
    join = source.split("async def join_lobby(", 1)[1].split("async def leave_lobby(", 1)[0]
    leave = source.split("async def leave_lobby(", 1)[1].split("async def player_count(", 1)[0]

    assert ".with_for_update()" in create
    assert "get_active_game(session, group_id=group.id, for_update=True)" in create
    assert "except IntegrityError" in create
    assert ".with_for_update()" in join
    assert "definition.max_players" in join
    assert "except IntegrityError" in join
    assert ".with_for_update()" in leave
    assert "lobby creator cannot leave" in leave


def test_game_models_are_registered_with_alembic_metadata() -> None:
    env = (ROOT / "alembic/env.py").read_text(encoding="utf-8")
    assert "from app.db import game_models  # noqa: F401" in env
