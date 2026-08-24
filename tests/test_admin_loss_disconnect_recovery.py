from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_onboarding_is_my_chat_member_production_winner() -> None:
    main = _source("app/main.py")
    assert main.index("group_onboarding_flow.router") < main.index("mimoru_identity.router")
    assert main.index("fun_preferences.router") < main.index("group_onboarding_flow.router")
    assert main.index("fun_extras.router") < main.index("group_onboarding_flow.router")
    assert "my_chat_member" not in _source("app/handlers/fun_preferences.py")
    assert "my_chat_member" not in _source("app/handlers/fun_extras.py")
    onboarding = _source("app/handlers/group_onboarding_flow.py")
    assert "@router.my_chat_member()" in onboarding


def test_admin_loss_persists_system_disconnect_before_attempt() -> None:
    onboarding = _source("app/handlers/group_onboarding_flow.py")
    body = onboarding.split("async def bot_group_membership_changed", 1)[1].split(
        "async def disconnect_group_crash_safe", 1
    )[0]
    branch = body.split(
        "if old_status == ChatMemberStatus.ADMINISTRATOR and new_status == ChatMemberStatus.MEMBER:",
        1,
    )[1].split("if new_status in INACTIVE_BOT_STATUSES", 1)[0]
    assert "await request_system_group_disconnect(session, group)" in branch
    assert "await attempt_group_disconnect(bot, group.id)" in branch
    assert branch.index("await request_system_group_disconnect(session, group)") < branch.index(
        "await attempt_group_disconnect(bot, group.id)"
    )
    assert "group.is_active = False" not in branch
    assert "await bot.leave_chat" not in branch


def test_system_disconnect_is_durable_and_owner_independent() -> None:
    service = _source("app/services/group_disconnects.py")
    assert "SYSTEM_DISCONNECT_ACTOR_ID = 0" in service
    request = service.split("async def request_system_group_disconnect", 1)[1].split(
        "async def _bot_membership_status", 1
    )[0]
    assert "SYSTEM_DISCONNECT_ACTOR_ID" in request
    persist = service.split("async def _persist_disconnect_intent", 1)[1].split(
        "async def request_group_disconnect", 1
    )[0]
    assert "await session.commit()" in persist


def test_system_recovery_rechecks_bot_state_before_leave() -> None:
    service = _source("app/services/group_disconnects.py")
    attempt = service.split("async def attempt_group_disconnect", 1)[1].split(
        "async def recover_group_disconnects", 1
    )[0]
    system = attempt.split(
        "if intent.actor_telegram_id == SYSTEM_DISCONNECT_ACTOR_ID:", 1
    )[1].split("elif (", 1)[0]
    assert "status = await _bot_membership_status(bot, chat_id)" in system
    assert "status == ChatMemberStatus.ADMINISTRATOR" in system
    assert "await session.delete(intent)" in system
    assert "status in ABSENT_STATUSES" in system
    assert "return await _finalize_disconnect(session, group, intent)" in system
    assert "status is None" in system
    assert 'intent.status = "pending"' in system
    assert attempt.index("_bot_membership_status(bot, chat_id)") < attempt.index(
        "await bot.leave_chat(chat_id)"
    )


def test_group_deactivation_remains_disconnect_finalization_only_for_admin_loss() -> None:
    service = _source("app/services/group_disconnects.py")
    finalize = service.split("async def _finalize_disconnect", 1)[1].split(
        "async def attempt_group_disconnect", 1
    )[0]
    assert "group.is_active = False" in finalize
    assert "await session.delete(intent)" in finalize
    assert "await session.commit()" in finalize

    onboarding = _source("app/handlers/group_onboarding_flow.py")
    membership = onboarding.split("async def bot_group_membership_changed", 1)[1].split(
        "async def disconnect_group_crash_safe", 1
    )[0]
    admin_loss = membership.split(
        "if old_status == ChatMemberStatus.ADMINISTRATOR and new_status == ChatMemberStatus.MEMBER:",
        1,
    )[1].split("if new_status in INACTIVE_BOT_STATUSES", 1)[0]
    assert "group.is_active = False" not in admin_loss
