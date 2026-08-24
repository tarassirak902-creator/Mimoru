from pathlib import Path

from app.services.moderation_reasons import normalize_actions

ROOT = Path(__file__).resolve().parents[1]


def test_kick_is_removed_from_reason_actions() -> None:
    assert normalize_actions(["warn", "kick", "mute", "kick", "ban"]) == ["warn", "mute", "ban"]


def test_retired_kick_buttons_are_filtered_at_send_boundary() -> None:
    source = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert '_RETIRED_KICK_CALLBACK_PREFIXES = ("reason_action:", "member_punish:", "role_perm:")' in source
    assert 'callback_data.endswith(":kick")' in source
    assert "if not _is_retired_kick_button(button)" in source
    assert "if cleaned_row:" in source


def test_kick_callbacks_are_guarded_before_legacy_handlers() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    router_block = main.split("dp.include_routers(", 1)[1]
    assert router_block.index("kick_retirement.router") < router_block.index("reason_admin.router")
    assert router_block.index("kick_retirement.router") < router_block.index("member_center.router")

    guard = (ROOT / "app/handlers/kick_retirement.py").read_text(encoding="utf-8")
    assert "reason_action:" in guard
    assert "member_punish:" in guard
    assert "role_perm:" in guard


def test_central_authorization_denies_kick_even_for_owner_paths() -> None:
    source = (ROOT / "app/services/access.py").read_text(encoding="utf-8")
    deny = source.index('if action == "kick":')
    owner = source.index("if group.owner_telegram_id == user_id", deny)
    assert deny < owner
    assert '"kick": False' in source
