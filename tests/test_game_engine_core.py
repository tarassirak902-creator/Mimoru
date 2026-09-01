from pathlib import Path

import pytest

from app.games.base import BaseGame
from app.games.config import GameDefinition
from app.games.registry import GameRegistry


ROOT = Path(__file__).resolve().parents[1]


class DummyGame(BaseGame):
    def __init__(self, definition: GameDefinition) -> None:
        self.definition = definition

    async def start(self, session, game) -> None:
        return None

    async def handle_action(
        self,
        session,
        game,
        *,
        actor_telegram_id: int,
        action: str,
        value: int | str | None = None,
    ) -> None:
        return None

    async def handle_timeout(self, session, game) -> None:
        return None

    async def restore(self, session, game) -> None:
        return None


def test_game_definition_validates_player_limits() -> None:
    game = GameDefinition(code="mafia", title="🐺 Мафия", min_players=4, max_players=15)
    assert game.code == "mafia"
    assert game.exclusive_group_game is True
    assert game.supports_rating is True

    with pytest.raises(ValueError):
        GameDefinition(code="broken", title="x", min_players=5, max_players=4)


def test_game_registry_requires_matching_executable_engine() -> None:
    registry = GameRegistry()
    definition = GameDefinition(code="dummy", title="Dummy", min_players=2, max_players=4)
    engine = DummyGame(definition)

    registry.register(definition, engine)
    assert registry.require("dummy") is definition
    assert registry.engine("dummy") is engine
    assert registry.require_entry("dummy").engine is engine
    assert registry.all() == (definition,)

    with pytest.raises(ValueError):
        registry.register(definition, engine)

    mismatch_definition = GameDefinition(code="other", title="Other", min_players=2, max_players=4)
    with pytest.raises(ValueError):
        GameRegistry().register(definition, DummyGame(mismatch_definition))

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


def test_game_manager_serializes_full_lobby_lifecycle() -> None:
    source = (ROOT / "app/games/manager.py").read_text(encoding="utf-8")
    create = source.split("async def create_lobby(", 1)[1].split("async def list_players(", 1)[0]
    join = source.split("async def join_lobby(", 1)[1].split("async def leave_lobby(", 1)[0]
    leave = source.split("async def leave_lobby(", 1)[1].split("async def start_lobby(", 1)[0]
    start = source.split("async def start_lobby(", 1)[1].split("async def cancel_game(", 1)[0]
    cancel = source.split("async def cancel_game(", 1)[1].split("async def player_count(", 1)[0]

    assert ".with_for_update()" in create
    assert "get_active_game(session, group_id=group.id, for_update=True)" in create
    assert "except IntegrityError" in create

    assert "get_game(session, game_id=game_id, for_update=True)" in join
    assert ".with_for_update()" in join
    assert "max_players = lobby_max_players(game, definition)" in join
    assert "len(joined) >= max_players" in join
    assert "existing.status = \"joined\"" in join
    assert "except IntegrityError" in join

    assert "get_game(session, game_id=game_id, for_update=True)" in leave
    assert ".with_for_update()" in leave
    assert "lobby creator cannot leave" in leave

    assert "get_game(session, game_id=game_id, for_update=True)" in start
    assert "list_players(session, game_id=game.id, for_update=True)" in start
    assert "definition.min_players" in start
    assert "GameSessionStatus.RUNNING.value" in start

    assert "get_game(session, game_id=game_id, for_update=True)" in cancel
    assert "GameSessionStatus.CANCELLED.value" in cancel
    assert "finished_at" in cancel


def test_game_callbacks_are_scoped_and_stale_safe() -> None:
    source = (ROOT / "app/games/handlers.py").read_text(encoding="utf-8")

    assert 'F.data.regexp(r"^gm:j:\\d+$")' in source
    assert 'F.data.regexp(r"^gm:l:\\d+$")' in source
    assert 'F.data.regexp(r"^gm:s:\\d+$")' in source
    assert 'F.data.regexp(r"^gm:c:\\d+$")' in source
    assert "callback.message.chat.id != group.telegram_chat_id" in source
    assert "❌ Эта кнопка больше не активна." in source
    assert "game.status != GameSessionStatus.LOBBY.value" in source
    assert "await can_manage_group(" in source
    assert "await manager.start_lobby(" in source
    assert "await manager.cancel_game(" in source


def test_game_models_are_registered_with_alembic_metadata() -> None:
    env = (ROOT / "alembic/env.py").read_text(encoding="utf-8")
    assert "from app.db import game_models  # noqa: F401" in env