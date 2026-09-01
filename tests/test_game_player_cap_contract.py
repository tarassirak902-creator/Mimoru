from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_player_cap_is_snapshotted_when_lobby_is_created() -> None:
    manager = read("app/games/manager.py")
    limits = read("app/games/group_limits.py")

    create = manager.split("async def create_lobby", 1)[1].split("async def list_players", 1)[0]
    join = manager.split("async def join_lobby", 1)[1].split("async def leave_lobby", 1)[0]

    assert 'PLAYER_CAP_KEY = "max_players"' in limits
    assert 'LOBBY_CAP_KEY = "lobby_max_players"' in limits
    assert "effective_max_players(definition, settings)" in create
    assert 'state_json={"lobby_max_players": max_players}' in create
    assert "lobby_max_players(game, definition)" in join
    assert "len(joined) >= max_players" in join


def test_lobby_renders_same_frozen_player_cap() -> None:
    source = read("app/games/lobby.py")
    block = source.split("async def lobby_text", 1)[1].split("async def ensure_lobby_message", 1)[0]

    assert "max_players = lobby_max_players(game, definition)" in block
    assert 'f"👥 Игроки: {len(players)}/{max_players}"' in block


def test_player_cap_admin_card_is_callback_driven_and_protected() -> None:
    handlers = read("app/games/limit_handlers.py")
    wiring = read("app/handlers/fun_preferences.py")

    assert 'Command("game_limit")' in handlers
    assert 'r"^gm:cap:\\d+:\\d+:(0|4|6|8|12|20)$"' in handlers
    assert "callback.from_user.id != requester_id" in handlers
    assert "can_manage_group(bot, group, callback.from_user.id, session)" in handlers
    assert "set_player_cap(settings, None if value == 0 else value)" in handlers
    assert "game_limit_handlers.router" in wiring


def test_group_cap_never_expands_or_breaks_game_definition() -> None:
    limits = read("app/games/group_limits.py")

    assert "return definition.max_players" in limits
    assert "max(definition.min_players, min(definition.max_players, cap))" in limits
    assert "max(definition.min_players, min(definition.max_players, value))" in limits
