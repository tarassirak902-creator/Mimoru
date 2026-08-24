from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_permission_match_compares_expected_fields_only():
    source = (ROOT / "app/services/chat_permission_transitions.py").read_text(encoding="utf-8")
    function = source.split("def permissions_match", 1)[1].split("async def _finalize", 1)[0]
    assert "expected = expected or {}" in function
    assert "actual_data = permissions_dict(actual)" in function
    assert "for key, value in expected.items()" in function


def test_permission_transition_commits_intent_before_locked_execution():
    source = (ROOT / "app/services/chat_permission_transitions.py").read_text(encoding="utf-8")
    function = source.split("async def apply_permission_transition", 1)[1].split(
        "async def recover_chat_permission_transitions", 1
    )[0]
    commit_pos = function.index("await session.commit()")
    execute_pos = function.index("return await _execute_live_transition(")
    assert commit_pos < execute_pos

    live = source.split("async def _execute_live_transition", 1)[1].split(
        "async def apply_permission_transition", 1
    )[0]
    assert "with_for_update()" in live
    assert "await bot.set_chat_permissions" in live


def test_recovery_never_writes_telegram_permissions():
    source = (ROOT / "app/services/chat_permission_transitions.py").read_text(encoding="utf-8")
    recovery = source.split("async def recover_chat_permission_transitions", 1)[1]
    assert "await bot.get_chat" in recovery
    assert "set_chat_permissions" not in recovery
    assert "permissions_match(chat.permissions, intent.desired_permissions)" in recovery
    assert "permissions_match(chat.permissions, intent.previous_permissions)" in recovery


def test_manual_permission_router_precedes_legacy_advanced_router():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "permission_modes.router," in main
    assert main.index("permission_modes.router,") < main.index("advanced.router,")


def test_hardened_delivery_scheduler_uses_safe_permission_tasks():
    leader = (ROOT / "app/services/background_leader.py").read_text(encoding="utf-8")
    assert "from app.tasks_delivery import background_loop" in leader
    safe_loop = (ROOT / "app/tasks_delivery.py").read_text(encoding="utf-8")
    assert "from app.tasks_permission_modes import apply_night_modes, expire_lockdowns" in safe_loop


def test_failed_background_restore_keeps_durable_state_for_retry():
    source = (ROOT / "app/tasks_permission_modes.py").read_text(encoding="utf-8")
    expire = source.split("async def expire_lockdowns", 1)[1].split("async def apply_night_modes", 1)[0]
    assert "apply_permission_transition" in expire
    assert "lockdown_enabled = False" not in expire
    assert "lockdown_previous_permissions = None" not in expire


def test_permission_transition_schema_is_registered():
    env = (ROOT / "alembic/env.py").read_text(encoding="utf-8")
    schema = (ROOT / "scripts/check_schema_consistency.py").read_text(encoding="utf-8")
    assert "permission_transition_models" in env
    assert "permission_transition_models" in schema
