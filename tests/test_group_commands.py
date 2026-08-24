from pathlib import Path

from app.handlers.group_commands import CLEAR_WARNING_WORDS, COMPLAINT_WORDS, parse_duration


ROOT = Path(__file__).resolve().parents[1]


def test_duration_parser_supports_group_friendly_units() -> None:
    assert parse_duration("30 секунд") == 30
    assert parse_duration("10 минут") == 600
    assert parse_duration("2 часа") == 7200
    assert parse_duration("1 день") == 86400
    assert parse_duration("без времени") is None


def test_group_commands_cover_requested_moderation_shortcuts() -> None:
    source = (ROOT / "app/handlers/group_commands.py").read_text(encoding="utf-8")
    assert '"говори"' in source
    assert '"разбан"' in source
    assert 'action = "mute"' in source
    assert 'action = "ban"' in source
    assert 'action = "kick"' not in source
    assert "|кик|" not in source
    assert 'action = "warn"' in source
    assert 'action = "unwarn"' in source
    assert "await can_moderate(bot, session, group, message.from_user.id, action)" in source
    assert "await execute(" in source


def test_group_shortcuts_recheck_live_telegram_admin_status() -> None:
    source = (ROOT / "app/handlers/group_commands.py").read_text(encoding="utf-8")
    assert "from app.services.access import can_moderate" in source
    assert "actor_has_permission" not in source
    assert 'await can_moderate(bot, session, group, message.from_user.id, "unmute")' in source
    assert 'await can_moderate(bot, session, group, message.from_user.id, "unwarn")' in source
    assert 'await can_moderate(bot, session, group, message.from_user.id, "unban")' in source
    assert "async def clear_all_warnings(message: Message, bot: Bot, session: AsyncSession)" in source


def test_all_warning_reset_and_public_complaints_are_supported() -> None:
    source = (ROOT / "app/handlers/group_commands.py").read_text(encoding="utf-8")
    assert "снять все предупреждения" in CLEAR_WARNING_WORDS
    assert "жалоба" in COMPLAINT_WORDS
    assert "Complaint(" in source
    assert "RankAssignment.rank_code.in_((DEPUTY_OWNER, CHIEF_ADMIN, CHAT_ADMIN))" in source
    assert 'action="unwarn_all"' not in source  # log_action is positional and must not be confused with moderation.execute
    assert '"unwarn_all"' in source


def test_group_command_router_precedes_legacy_helper_report() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    router_block = main.split("dp.include_routers(", 1)[1]
    assert router_block.index("group_commands.router") < router_block.index("telegram_roles.router")


def test_unmute_combined_handler_exists() -> None:
    source = (ROOT / "app/handlers/group_commands.py").read_text(encoding="utf-8")
    assert "async def unmute_combined" in source
    assert "resolve_target_user(" in source
    assert 'await can_moderate(bot, session, group, message.from_user.id, "unmute")' in source
    assert "await execute(" in source
    assert 'action="unmute"' in source


def test_unmute_combined_uses_public_user_token_for_moderator() -> None:
    source = (ROOT / "app/handlers/group_commands.py").read_text(encoding="utf-8")
    assert "from app.services.public_identity import public_user_token" in source
    assert "moderator_name=public_user_token(message.from_user.id)" in source


def test_unmute_combined_handles_no_target() -> None:
    source = (ROOT / "app/handlers/group_commands.py").read_text(encoding="utf-8")
    assert "Укажите пользователя" in source


def test_unmute_combined_exists() -> None:
    source = (ROOT / "app/handlers/group_commands.py").read_text(encoding="utf-8")
    assert '"говори"' in source
    assert "async def unmute_combined" in source


def test_unban_combined_handler_exists() -> None:
    source = (ROOT / "app/handlers/group_commands.py").read_text(encoding="utf-8")
    assert "async def unban_combined" in source
    assert "resolve_target_user(" in source
    assert 'action="unban"' in source
