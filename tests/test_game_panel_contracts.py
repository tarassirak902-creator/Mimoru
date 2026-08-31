from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_games_command_is_owned_by_game_engine() -> None:
    game_handlers = (ROOT / "app/games/handlers.py").read_text(encoding="utf-8")
    text_entry = (ROOT / "app/games/text_entry.py").read_text(encoding="utf-8")
    entertainment = (ROOT / "app/handlers/fun_preferences.py").read_text(encoding="utf-8")

    assert '@router.message(Command("games")' in game_handlers
    assert '@router.message(Command("games")' not in text_entry
    assert 'Command("games")' not in entertainment
    assert "router.include_router(game_text_entry.router)" in entertainment
    assert "router.include_router(game_handlers.router)" in entertainment
    assert entertainment.index("game_text_entry.router") < entertainment.index("game_handlers.router")


def test_games_text_alias_is_exact_and_owned_by_game_engine() -> None:
    source = (ROOT / "app/games/text_entry.py").read_text(encoding="utf-8")
    entertainment = (ROOT / "app/handlers/fun_preferences.py").read_text(encoding="utf-8")

    assert 'F.text.regexp(r"(?i)^игры$")' in source
    assert "какие игры" not in source.casefold()
    assert "router.include_router(game_text_entry.router)" in entertainment
    assert entertainment.index("game_text_entry.router") < entertainment.index("game_handlers.router")


def test_game_center_entries_send_visible_snapshot() -> None:
    helper = (ROOT / "app/games/game_center.py").read_text(encoding="utf-8")
    command = (ROOT / "app/games/handlers.py").read_text(encoding="utf-8")
    text_entry = (ROOT / "app/games/text_entry.py").read_text(encoding="utf-8")

    assert "await ensure_game_panel(bot, session, group=group)" in helper
    assert "active_game_for_group(session, group.id)" in helper
    assert "await bot.send_message(" in helper
    assert "panel_text(active_game=active_game)" in helper
    assert "panel_markup(active_game=active_game)" in helper
    assert "reply_to_message_id=reply_to_message_id" in helper
    assert "await send_game_center_snapshot(" in command
    assert "reply_to_message_id=message.message_id" in command
    assert "await send_game_center_snapshot(" in text_entry
    assert "reply_to_message_id=message.message_id" in text_entry


def test_game_router_does_not_capture_ordinary_group_text() -> None:
    source = (ROOT / "app/games/handlers.py").read_text(encoding="utf-8")
    assert "F.text.casefold()" not in source
    assert 'F.data == "gm:home"' in source
    assert 'F.data == "gm:list"' in source
    assert 'r"^gm:new:' in source


def test_game_panel_is_edit_first_and_pin_is_best_effort() -> None:
    source = (ROOT / "app/games/panels.py").read_text(encoding="utf-8")
    ensure = source.split("async def ensure_game_panel(", 1)[1].split("async def render_profile(", 1)[0]

    assert ensure.index("bot.edit_message_text(") < ensure.index("bot.send_message(")
    assert "message is not modified" in ensure
    assert "bot.pin_chat_message(" in ensure
    assert "except (TelegramBadRequest, TelegramForbiddenError)" in ensure
    assert "game_panel_pin_skipped" in ensure


def test_game_panel_has_single_persistent_group_key() -> None:
    models = (ROOT / "app/db/game_models.py").read_text(encoding="utf-8")
    panel = models.split("class GamePanel", 1)[1].split("class GameSession", 1)[0]
    assert 'ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True' in panel
    assert "message_id" in panel


def test_open_active_game_synchronizes_real_game_ui() -> None:
    source = (ROOT / "app/games/handlers.py").read_text(encoding="utf-8")
    handler = source.split("async def game_open(", 1)[1]

    assert 'r"^gm:open:' in source
    assert "game_registry.get_entry(game.game_type)" in handler
    assert 'getattr(entry.engine, "sync_ui", None)' in handler
    assert "await sync_ui(bot, session, game)" in handler
    assert "game_open_sync_failed" in handler
    assert "Актуальная карточка игры обновлена" in handler
