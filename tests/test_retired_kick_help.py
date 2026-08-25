from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_help_sanitizes_legacy_panel_only_when_needed():
    retirement = (ROOT / "app/handlers/kick_retirement.py").read_text(encoding="utf-8")
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    home = (ROOT / "app/handlers/home_panel.py").read_text(encoding="utf-8")
    common = (ROOT / "app/handlers/common.py").read_text(encoding="utf-8")

    # Current user-facing help is correct in source and does not rely on import
    # order or runtime monkey-patching.
    assert "пред, мут 2ч, кик или бан." not in home
    assert "пред, мут 2ч, кик или бан." not in common
    assert "пред, мут 2ч или бан." in home
    assert "пред, мут 2ч или бан." in common

    # The legacy panel is still sanitized for old/secondary handler paths.
    assert '"app.handlers.panel"' in retirement
    assert '"COMMANDS_TEXT"' in retirement

    # The guided home handler is the actual first panel:commands winner.
    assert 'F.data == "panel:commands"' in home
    assert main.index("\n        home_panel.router,") < main.index("\n        panel.router,")


def test_public_command_reference_does_not_advertise_kick():
    commands = (ROOT / "COMMANDS_RU.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    matrix = (ROOT / "FUNCTIONALITY_MATRIX.md").read_text(encoding="utf-8")
    assert "`кик`" not in commands
    assert "бан, разбан, мут, размут, кик" not in readme
    assert "Бан/разбан/кик" not in matrix


def test_historical_kick_log_label_is_preserved():
    panel = (ROOT / "app/handlers/panel.py").read_text(encoding="utf-8")
    assert '"kick": "кик"' in panel
