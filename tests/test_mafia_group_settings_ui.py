from pathlib import Path
from types import SimpleNamespace

from app.games.settings_handlers import (
    _mafia_timer_values,
    _next_mafia_timer_value,
    mafia_reset_markup,
    mafia_reset_text,
    mafia_settings_markup,
    mafia_settings_text,
    mafia_timer_settings_markup,
    mafia_timer_settings_text,
)


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
        "gm:cfg:mafia:timers",
        "gm:cfg:mafia:reset",
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


def test_mafia_timer_defaults_match_game_engine_defaults() -> None:
    timers = _mafia_timer_values(None)
    text = mafia_timer_settings_text(None)
    callbacks = _callbacks(mafia_timer_settings_markup(None))

    assert timers == {
        "day_start": 15,
        "discussion": 90,
        "voting": 60,
        "result": 10,
        "night_start": 10,
        "night": 60,
    }
    assert "Старт дня: 15 с" in text
    assert "Обсуждение: 90 с" in text
    assert "Голосование: 60 с" in text
    assert "Показ результата: 10 с" in text
    assert "Старт ночи: 10 с" in text
    assert "Ночные действия: 60 с" in text
    assert callbacks == [
        "gm:cfg:mafia:timer:day_start",
        "gm:cfg:mafia:timer:discussion",
        "gm:cfg:mafia:timer:voting",
        "gm:cfg:mafia:timer:result",
        "gm:cfg:mafia:timer:night_start",
        "gm:cfg:mafia:timer:night",
        "gm:cfg:mafia",
    ]


def test_mafia_timer_values_use_persisted_engine_keys_and_safe_defaults() -> None:
    timers = _mafia_timer_values(_settings({
        "day_start_seconds": 30,
        "discussion_seconds": 180,
        "voting_seconds": 120,
        "result_seconds": 20,
        "night_start_seconds": 15,
        "night_seconds": 90,
    }))
    assert timers == {
        "day_start": 30,
        "discussion": 180,
        "voting": 120,
        "result": 20,
        "night_start": 15,
        "night": 90,
    }

    invalid = _mafia_timer_values(_settings({
        "day_start_seconds": "oops",
        "discussion_seconds": 17,
        "night_seconds": 999,
    }))
    assert invalid["day_start"] == 15
    assert invalid["discussion"] == 90
    assert invalid["night"] == 60


def test_mafia_timer_presets_cycle_and_persist_under_existing_mafia_json() -> None:
    assert _next_mafia_timer_value("discussion", 90) == 120
    assert _next_mafia_timer_value("discussion", 300) == 30
    assert _next_mafia_timer_value("discussion", 17) == 90

    source = (ROOT / "app/games/settings_handlers.py").read_text(encoding="utf-8")
    toggle = source.split("async def mafia_timer_settings_toggle", 1)[1]
    for key in (
        "day_start_seconds",
        "discussion_seconds",
        "voting_seconds",
        "result_seconds",
        "night_start_seconds",
        "night_seconds",
    ):
        assert key in source
    assert "all_settings = dict(settings.settings_json or {})" in toggle
    assert 'mafia = dict(all_settings.get("mafia") or {})' in toggle
    assert 'all_settings["mafia"] = mafia' in toggle
    assert "settings.settings_json = all_settings" in toggle
    assert "await session.commit()" in toggle


def test_mafia_engine_timer_defaults_and_bounds_stay_aligned_with_ui() -> None:
    source = (ROOT / "app/games/mafia/game.py").read_text(encoding="utf-8")

    assert 'mafia_settings.get("day_start_seconds"), 15, 3, 120' in source
    assert 'mafia_settings.get("discussion_seconds"), 90, 15, 600' in source
    assert 'mafia_settings.get("voting_seconds"), 60, 15, 300' in source
    assert 'mafia_settings.get("result_seconds"), 10, 3, 60' in source
    assert 'mafia_settings.get("night_start_seconds"), 10, 3, 60' in source
    assert 'mafia_settings.get("night_seconds"), 60, 15, 300' in source


def test_mafia_reset_requires_explicit_confirmation() -> None:
    text = mafia_reset_text()
    callbacks = _callbacks(mafia_reset_markup())

    assert "стандартные правила Доктора" in text
    assert "Общие настройки игр" in text
    assert callbacks == [
        "gm:cfg:mafia:reset:confirm",
        "gm:cfg:mafia",
    ]


def test_mafia_reset_only_removes_mafia_subtree_under_locked_admin_path() -> None:
    source = (ROOT / "app/games/settings_handlers.py").read_text(encoding="utf-8")
    prompt = source.split("async def mafia_settings_reset_prompt", 1)[1].split(
        "async def game_settings_toggle", 1
    )[0]
    confirm = source.split("async def mafia_settings_reset_confirm", 1)[1]

    assert "_managed_group(" in prompt
    assert "mafia_reset_text()" in prompt
    assert "mafia_reset_markup()" in prompt
    assert "_managed_group(" in confirm
    assert "_locked_settings(" in confirm
    assert "all_settings = dict(settings.settings_json or {})" in confirm
    assert 'all_settings.pop("mafia", None)' in confirm
    assert "settings.settings_json = all_settings" in confirm
    assert "settings.settings_json = {}" not in confirm
    assert "await session.commit()" in confirm
