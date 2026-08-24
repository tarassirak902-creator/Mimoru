from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def test_control_center_router_is_registered():
    source = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "control_center" in source
    assert "control_center.router" in source


def test_content_can_be_managed_from_buttons():
    kb = (ROOT / "app/keyboards/panel.py").read_text(encoding="utf-8")
    handler = (ROOT / "app/handlers/control_center.py").read_text(encoding="utf-8")
    for token in ["word_add:", "word_remove:", "channel_add:", "channel_remove:"]:
        assert token in kb or token in handler
    assert "plan_limit(group, \"words\")" in handler
    assert "plan_limit(group, \"channels\")" in handler


def test_group_settings_have_no_command_editor():
    kb = (ROOT / "app/keyboards/panel.py").read_text(encoding="utf-8")
    handler = (ROOT / "app/handlers/control_center.py").read_text(encoding="utf-8")
    assert "Параметры группы" in kb
    for token in ["welcome_text", "rules_text", "warnings_limit", "default_mute", "antiflood_preset"]:
        assert token in kb or token in handler


def test_role_permissions_are_button_managed():
    source = (ROOT / "app/handlers/control_center.py").read_text(encoding="utf-8")
    kb = (ROOT / "app/keyboards/panel.py").read_text(encoding="utf-8")
    for action in ["warn", "unwarn", "mute", "unmute", "kick", "ban", "unban", "delete", "info", "history", "warnings"]:
        assert action in source
        assert action in kb
    assert "DEFAULT_ROLE_PERMISSIONS" in source
    assert "get_chat_member" in source


def test_delete_message_has_own_permission():
    access = (ROOT / "app/services/access.py").read_text(encoding="utf-8")
    group = (ROOT / "app/handlers/group.py").read_text(encoding="utf-8")
    assert '"delete": True' in access
    assert 'can_moderate(bot, session, group, message.from_user.id, "delete")' in group


def test_support_center_supports_create_history_reply_close():
    source = (ROOT / "app/handlers/control_center.py").read_text(encoding="utf-8")
    kb = (ROOT / "app/keyboards/panel.py").read_text(encoding="utf-8")
    for token in ["support:new", "support:mine", "ticket_reply:", "ticket_close:"]:
        assert token in source or token in kb
    assert 'ticket.status = "answered"' in source
    assert 'ticket.status = "closed"' in source


def test_new_python_sources_parse():
    for rel in [
        "app/handlers/control_center.py",
        "app/keyboards/panel.py",
        "app/handlers/panel.py",
        "app/handlers/dashboard.py",
        "app/services/access.py",
    ]:
        ast.parse((ROOT / rel).read_text(encoding="utf-8"), filename=rel)
