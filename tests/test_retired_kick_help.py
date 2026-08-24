from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_help_sanitizes_actual_home_panel_winner_and_legacy_panel():
    retirement = (ROOT / "app/handlers/kick_retirement.py").read_text(encoding="utf-8")
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    home = (ROOT / "app/handlers/home_panel.py").read_text(encoding="utf-8")

    assert '"app.handlers.home_panel"' in retirement
    assert '"HELP_TEXT"' in retirement
    assert '("пред, мут 2ч, кик или бан.", "пред, мут 2ч или бан.")' in retirement
    assert '"app.handlers.panel"' in retirement
    assert '"COMMANDS_TEXT"' in retirement

    # The guided home handler is the actual first panel:commands winner.
    assert 'F.data == "panel:commands"' in home
    assert main.index("\n        home_panel.router,") < main.index("\n        panel.router,")

    # Both help modules are imported before kick_retirement performs the sanitization.
    retirement_import = main.index("from app.handlers import kick_retirement")
    assert main.index("home_panel") < retirement_import
    assert main.index(", panel, permission_modes") < retirement_import


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
