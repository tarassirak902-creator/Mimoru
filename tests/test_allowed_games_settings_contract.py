from pathlib import Path
from types import SimpleNamespace

from app.games.settings_handlers import (
    _effective_allowed_games,
    _game_codes,
    allowed_games_markup,
)


ROOT = Path(__file__).resolve().parents[1]


def test_empty_allowlist_means_all_registered_games() -> None:
    codes = _game_codes()
    assert len(codes) == 10
    assert _effective_allowed_games(None) == set(codes)
    assert _effective_allowed_games(SimpleNamespace(allowed_games=[])) == set(codes)


def test_explicit_allowlist_is_respected() -> None:
    codes = _game_codes()
    selected = codes[:3]
    settings = SimpleNamespace(allowed_games=selected)
    assert _effective_allowed_games(settings) == set(selected)


def test_allowed_games_keyboard_is_compact_and_dynamic() -> None:
    markup = allowed_games_markup(None)
    game_rows = markup.inline_keyboard[:-1]
    assert all(1 <= len(row) <= 2 for row in game_rows)
    callbacks = [button.callback_data for row in game_rows for button in row]
    assert callbacks == [f"gm:cfg:game:{code}" for code in _game_codes()]
    assert markup.inline_keyboard[-1][0].callback_data == "gm:settings"


def test_toggle_contract_preserves_global_disable_semantics() -> None:
    source = (ROOT / "app/games/settings_handlers.py").read_text(encoding="utf-8")
    create_source = (ROOT / "app/games/handlers.py").read_text(encoding="utf-8")
    assert 'F.data == "gm:cfg:games"' in source
    assert 'r"^gm:cfg:game:[a-z0-9_]{1,32}$"' in source
    assert "if len(allowed) <= 1:" in source
    assert "settings.allowed_games = [] if allowed == set(all_codes)" in source
    assert "if settings is not None and settings.allowed_games and code not in settings.allowed_games:" in create_source
