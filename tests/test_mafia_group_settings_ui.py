from pathlib import Path
from types import SimpleNamespace

from app.games.settings_handlers import mafia_settings_markup, mafia_settings_text


ROOT = Path(__file__).resolve().parents[1]


def _callbacks(markup) -> list[str]:
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data is not None
    ]


def _settings(mafia: dict) -> SimpleNamespace:
    return SimpleNamespace(settings_json={"mafia": mafia})


def test_mafia_settings_defaults_match_game_engine_defaults() -> None:
    text = mafia_settings_text(None)
    callbacks = _callbacks(mafia_settings_markup(None))

    assert "Доктор лечит себя: да" in text
    assert "одну цель две ночи подряд: нет" in text
    assert "после 2 пропущенных" in text
    assert callbacks == [
        "gm:cfg:mafia:self",
        "gm:cfg:mafia:repeat",
        "gm:cfg:mafia:afk",
        "gm:settings",
    ]


def test_mafia_settings_render_persisted_values() -> None:
    text = mafia_settings_text(_settings({
        "doctor_can_self_heal": False,
        "doctor_can_heal_same_player_twice": True,
        "afk_strikes_to_remove": 4,
    }))

    assert "Доктор лечит себя: нет" in text
    assert "одну цель две ночи подряд: да" in text
    assert "после 4 пропущенных" in text


def test_mafia_settings_are_persisted_under_mafia_json_without_replacing_other_settings() -> None:
    source = (ROOT / "app/games/settings_handlers.py").read_text(encoding="utf-8")
    toggle = source.split("async def mafia_settings_toggle", 1)[1]

    assert "all_settings = dict(settings.settings_json or {})" in toggle
    assert 'mafia = dict(all_settings.get("mafia") or {})' in toggle
    assert 'mafia["doctor_can_self_heal"]' in toggle
    assert 'mafia["doctor_can_heal_same_player_twice"]' in toggle
    assert 'mafia["afk_strikes_to_remove"]' in toggle
    assert 'all_settings["mafia"] = mafia' in toggle
    assert "settings.settings_json = all_settings" in toggle
    assert "1 if afk_strikes >= 5 else afk_strikes + 1" in toggle


def test_mafia_engine_reads_the_same_setting_keys_at_start() -> None:
    source = (ROOT / "app/games/mafia/game.py").read_text(encoding="utf-8")

    assert 'mafia_settings.get("doctor_can_self_heal", True)' in source
    assert 'mafia_settings.get("doctor_can_heal_same_player_twice", False)' in source
    assert 'mafia_settings.get("afk_strikes_to_remove")' in source
