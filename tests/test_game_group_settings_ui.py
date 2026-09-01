from pathlib import Path
from types import SimpleNamespace

from app.games.settings_handlers import settings_markup, settings_text


ROOT = Path(__file__).resolve().parents[1]


def _callbacks(markup) -> list[str]:
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data is not None
    ]


def test_game_settings_default_view_matches_model_defaults() -> None:
    text = settings_text(None)
    callbacks = _callbacks(settings_markup(None))

    assert "🎮 Игры: включены" in text
    assert "🏆 Рейтинг: включён" in text
    assert "создатель лобби или администратор" in text
    assert callbacks == [
        "gm:cfg:enabled",
        "gm:cfg:rating",
        "gm:cfg:creator",
        "gm:cfg:mafia",
        "gm:home",
    ]


def test_game_settings_render_changed_values() -> None:
    settings = SimpleNamespace(
        enabled=False,
        rating_enabled=False,
        creator_policy="any_at_min",
    )
    text = settings_text(settings)

    assert "🎮 Игры: выключены" in text
    assert "🏆 Рейтинг: выключен" in text
    assert "любой участник лобби после набора минимума" in text


def test_game_settings_callbacks_require_management_and_shared_locked_writes() -> None:
    source = (ROOT / "app/games/settings_handlers.py").read_text(encoding="utf-8")
    lock_helper = source.split("async def _locked_settings", 1)[1].split("async def _render", 1)[0]
    generic_toggle = source.split("async def game_settings_toggle", 1)[1].split(
        "async def mafia_settings_toggle", 1
    )[0]

    assert "can_manage_group(" in source
    assert ".with_for_update()" in lock_helper
    assert "GameGroupSettings(" in lock_helper
    assert "await session.flush()" in lock_helper
    assert "await _locked_settings(session, group_id=group.id)" in generic_toggle
    assert "await session.commit()" in generic_toggle


def test_game_settings_router_precedes_generic_game_router() -> None:
    source = (ROOT / "app/handlers/fun_preferences.py").read_text(encoding="utf-8")

    assert "game_settings_handlers" in source
    assert source.index("game_settings_handlers.router") < source.index("game_handlers.router")


def test_game_center_exposes_settings_entry() -> None:
    source = (ROOT / "app/games/panels.py").read_text(encoding="utf-8")

    assert 'text="⚙️ Настройки", callback_data="gm:settings"' in source
