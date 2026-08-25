from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_setup_wizard_has_back_navigation_on_every_nested_step() -> None:
    source = (ROOT / "app/handlers/wizard_navigation.py").read_text(encoding="utf-8")
    assert 'callback_data=f"setupnav:{group_id}:step1"' in source
    assert 'f"setupnav:{group_id}:step{step - 1}:{profile}:{level}"' in source
    assert 'f"setupnav:{group_id}:step2:{profile}"' in source
    assert 'callback_data=f"group_section:{group_id}:settings"' in source


def test_old_setup_start_buttons_enter_reversible_wizard() -> None:
    source = (ROOT / "app/handlers/wizard_navigation.py").read_text(encoding="utf-8")
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert 'F.data.regexp(r"^setup:\\d+:start$")' in source
    assert main.index("\n        wizard_navigation.router,") < main.index("\n        navigation_fixes.router,")
    assert main.index("\n        wizard_navigation.router,") < main.index("\n        onboarding.router,")


def test_wizard_finish_returns_to_settings_or_group() -> None:
    source = (ROOT / "app/handlers/wizard_navigation.py").read_text(encoding="utf-8")
    assert 'callback_data=f"group_section:{group.id}:settings"' in source
    assert 'callback_data=f"group:{group.id}"' in source
