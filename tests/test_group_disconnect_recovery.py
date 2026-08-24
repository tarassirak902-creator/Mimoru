from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_disconnect_intent_is_committed_before_telegram_leave():
    service = (ROOT / "app/services/group_disconnects.py").read_text(encoding="utf-8")
    persist = service.split("async def _persist_disconnect_intent", 1)[1].split(
        "async def request_group_disconnect", 1
    )[0]
    request = service.split("async def request_group_disconnect", 1)[1].split(
        "async def request_system_group_disconnect", 1
    )[0]
    assert "await session.commit()" in persist
    assert "await _persist_disconnect_intent" in request

    handler = (ROOT / "app/handlers/group_onboarding_flow.py").read_text(encoding="utf-8")
    function = handler.split("async def disconnect_group_crash_safe", 1)[1].split(
        "@router.message", 1
    )[0]
    request_pos = function.index("await request_group_disconnect")
    attempt_pos = function.index("await attempt_group_disconnect")
    assert request_pos < attempt_pos


def test_group_is_only_deactivated_by_disconnect_finalization():
    service = (ROOT / "app/services/group_disconnects.py").read_text(encoding="utf-8")
    attempt = service.split("async def attempt_group_disconnect", 1)[1].split(
        "async def recover_group_disconnects", 1
    )[0]
    finalize = service.split("async def _finalize_disconnect", 1)[1].split(
        "async def attempt_group_disconnect", 1
    )[0]
    assert "group.is_active = False" not in attempt
    assert "group.is_active = False" in finalize
    assert "await bot.leave_chat" in attempt
    assert "await _bot_is_absent" in attempt


def test_retryable_leave_failure_preserves_disconnect_intent():
    service = (ROOT / "app/services/group_disconnects.py").read_text(encoding="utf-8")
    attempt = service.split("async def attempt_group_disconnect", 1)[1].split(
        "async def recover_group_disconnects", 1
    )[0]
    error_branch = attempt.split("except (TelegramBadRequest, TelegramForbiddenError) as error:", 1)[1]
    assert 'intent.status = "pending"' in error_branch
    assert "intent.error_text" in error_branch
    assert "return False" in error_branch


def test_leader_recovers_disconnect_intents_before_scheduled_worker():
    leader = (ROOT / "app/services/background_leader.py").read_text(encoding="utf-8")
    worker = leader.split("async def _run_leader_worker", 1)[1].split(
        "async def leader_background_loop", 1
    )[0]
    recover_pos = worker.index("await recover_group_disconnects(bot)")
    loop_pos = worker.index("await background_loop(bot, redis, local_stop)")
    assert recover_pos < loop_pos


def test_safe_disconnect_callback_wins_over_legacy_handler():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    onboarding = (ROOT / "app/handlers/group_onboarding_flow.py").read_text(encoding="utf-8")
    contracts = (ROOT / "scripts/audit_handler_contracts.py").read_text(encoding="utf-8")
    assert 'F.data.regexp(r"^group_disconnect_do:\\d+$")' in onboarding
    assert main.index("group_onboarding_flow.router") < main.index("group_shortcuts.router")
    assert 'group_onboarding_flow.disconnect_group_crash_safe' in contracts


def test_disconnect_intent_schema_is_registered():
    migration = (ROOT / "alembic/versions/0044_group_disconnect_intents.py").read_text(encoding="utf-8")
    env = (ROOT / "alembic/env.py").read_text(encoding="utf-8")
    schema = (ROOT / "scripts/check_schema_consistency.py").read_text(encoding="utf-8")
    assert '"group_disconnect_intents"' in migration
    assert "group_disconnect_models" in env
    assert "group_disconnect_models" in schema
