from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_manual_plan_helper_locks_group_before_expiry_mutation() -> None:
    source = (ROOT / "app/handlers/service_management_fixes.py").read_text(encoding="utf-8")
    lock_helper = source.split("async def _locked_group", 1)[1].split(
        "async def _apply_manual_plan", 1
    )[0]
    apply_helper = source.split("async def _apply_manual_plan", 1)[1].split(
        "async def _render_plan_result", 1
    )[0]
    assert ".with_for_update()" in lock_helper
    lock_call = apply_helper.index("group = await _locked_group")
    expiry_read = apply_helper.index("group.plan_expires_at")
    plan_write = apply_helper.index("group.plan_code =")
    event_add = apply_helper.index("session.add(GroupSubscriptionEvent(")
    commit = apply_helper.index("await session.commit()")
    assert lock_call < expiry_read
    assert lock_call < plan_write < event_add < commit


def test_live_service_plan_apply_uses_serialized_hardened_winner() -> None:
    source = (ROOT / "app/handlers/service_management_fixes.py").read_text(encoding="utf-8")
    audit = (ROOT / "scripts/audit_handler_contracts.py").read_text(encoding="utf-8")
    assert 'F.data.regexp(r"^service_plan_apply:\\d+:(trial|standard|pro|free):(0|7|30)$")' in source
    assert "async def service_plan_apply_serialized" in source
    assert "group = await _apply_manual_plan(" in source
    assert "service_management_fixes.service_plan_apply_serialized" in audit


def test_all_manual_plan_callbacks_share_locked_mutation_helper() -> None:
    source = (ROOT / "app/handlers/service_management_fixes.py").read_text(encoding="utf-8")
    apply_handler = source.split("async def service_plan_apply_serialized", 1)[1].split(
        "@router.callback_query(F.data.regexp(r\"^service_plan_action", 1
    )[0]
    action_handler = source.split("async def service_plan_action_fixed", 1)[1]
    assert "await _apply_manual_plan(" in apply_handler
    assert "await _apply_manual_plan(" in action_handler


def test_legacy_trial_text_uses_serialized_hardened_winner() -> None:
    source = (ROOT / "app/handlers/service_management_fixes.py").read_text(encoding="utf-8")
    main_source = (ROOT / "app/main.py").read_text(encoding="utf-8")
    handler = source.split("async def grant_trial_serialized", 1)[1].split(
        "@router.callback_query", 1
    )[0]

    assert 'F.text.regexp(r"(?i)^тестовый период \\d+ \\d+д$")' in source
    assert "is_service_owner(message.from_user.id)" in handler
    assert "group = await _apply_manual_plan(" in handler
    assert 'plan_code="trial"' in handler
    assert "group.plan_code =" not in handler
    assert "group.plan_expires_at =" not in handler
    assert main_source.index("service_management_fixes.router") < main_source.index(
        "client_management.router"
    )
