from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_connect_checks_bot_admin_before_any_db_mutation() -> None:
    handler = _source("app/handlers/group_onboarding_flow.py")
    body = handler.split("async def connect_group_private_first", 1)[1].split(
        "async def open_connected_group_setup", 1
    )[0]
    assert "await is_creator(" in body
    assert "bot_admin = await _bot_admin_status(" in body
    assert "await upsert_user(" in body
    assert "await get_or_create_group(" in body
    assert body.index("bot_admin = await _bot_admin_status(") < body.index("await upsert_user(")
    assert body.index("bot_admin = await _bot_admin_status(") < body.index("await get_or_create_group(")


def test_connect_refuses_member_or_unknown_bot_state_before_activation() -> None:
    handler = _source("app/handlers/group_onboarding_flow.py")
    helper = handler.split("async def _bot_admin_status", 1)[1].split(
        "@router.my_chat_member()", 1
    )[0]
    assert "await bot.get_chat_member(chat_id, bot.id)" in helper
    assert "except (TelegramBadRequest, TelegramForbiddenError):" in helper
    assert "return None" in helper
    assert "member.status == ChatMemberStatus.ADMINISTRATOR" in helper

    connect = handler.split("async def connect_group_private_first", 1)[1].split(
        "async def open_connected_group_setup", 1
    )[0]
    unknown = connect.split("if bot_admin is None:", 1)[1].split("if not bot_admin:", 1)[0]
    member = connect.split("if not bot_admin:", 1)[1].split("await upsert_user(", 1)[0]
    assert "return" in unknown
    assert "return" in member
    assert "get_or_create_group" not in unknown
    assert "get_or_create_group" not in member


def test_membership_ui_requires_promotion_before_connect_prompt() -> None:
    handler = _source("app/handlers/group_onboarding_flow.py")
    membership = handler.split("async def bot_group_membership_changed", 1)[1].split(
        "async def disconnect_group_crash_safe", 1
    )[0]
    promoted = membership.split(
        "if new_status == ChatMemberStatus.ADMINISTRATOR and old_status != ChatMemberStatus.ADMINISTRATOR:",
        1,
    )[1].split("if old_status in INACTIVE_BOT_STATUSES", 1)[0]
    member = membership.split(
        "if old_status in INACTIVE_BOT_STATUSES and new_status == ChatMemberStatus.MEMBER:",
        1,
    )[1].split("group = await session.scalar", 1)[0]
    assert "подключить" in promoted
    assert "получила права администратора" in promoted
    assert "назначьте Mimoru администратором" in member


def test_admin_ready_success_preserves_blocked_owner_serialization() -> None:
    handler = _source("app/handlers/group_onboarding_flow.py")
    connect = handler.split("async def connect_group_private_first", 1)[1].split(
        "async def open_connected_group_setup", 1
    )[0]
    assert connect.index("if not bot_admin:") < connect.index("await upsert_user(")
    assert connect.index("await upsert_user(") < connect.index("await get_or_create_group(")
    assert "except GroupOwnerServiceBlockedError:" in connect
    assert connect.index("await get_or_create_group(") < connect.index(
        "sync = await sync_telegram_administrators"
    )
    assert connect.index("sync = await sync_telegram_administrators") < connect.index(
        "await session.commit()"
    )
    assert connect.index("await session.commit()") < connect.index(
        'await message.reply("✅ Группа подключена к Mimoru."'
    )
