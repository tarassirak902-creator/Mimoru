from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _function(source: str, name: str) -> str:
    body = source.split(f"async def {name}(", 1)[1]
    boundaries = [
        index
        for marker in ("\nasync def ", "\n@router.")
        if (index := body.find(marker)) >= 0
    ]
    return body[: min(boundaries)] if boundaries else body


def test_lockdown_expiry_rechecks_under_group_lock_before_transition() -> None:
    source = (ROOT / "app/tasks_permission_modes.py").read_text(encoding="utf-8")
    body = _function(source, "expire_lockdowns")

    candidate_scan = body.index("select(Group.id)")
    group_lock = body.index("select(Group)", candidate_scan + 1)
    for_update = body.index(".with_for_update()", group_lock)
    enabled_recheck = body.index("not group.settings.lockdown_enabled", for_update)
    deadline_recheck = body.index("group.settings.lockdown_until > now", enabled_recheck)
    current_permissions = body.index("await _current_permissions", deadline_recheck)
    transition = body.index("await apply_permission_transition(", current_permissions)

    assert candidate_scan < group_lock < for_update < enabled_recheck < deadline_recheck
    assert deadline_recheck < current_permissions < transition


def test_night_mode_decision_is_made_after_group_lock() -> None:
    source = (ROOT / "app/tasks_permission_modes.py").read_text(encoding="utf-8")
    body = _function(source, "apply_night_modes")

    group_lock = body.index("select(Group)", body.index("for group_id in group_ids:"))
    for_update = body.index(".with_for_update()", group_lock)
    settings = body.index("settings = group.settings", for_update)
    should_lock = body.index("should_lock =", settings)
    night_lock = body.index('operation="night_lock"', should_lock)
    night_unlock = body.index('operation="night_unlock"', night_lock)
    assert group_lock < for_update < settings < should_lock < night_lock < night_unlock


def test_executor_revalidates_automatic_intent_after_durable_commit() -> None:
    source = (ROOT / "app/services/chat_permission_transitions.py").read_text(encoding="utf-8")
    apply_body = _function(source, "apply_permission_transition")
    durable_commit = apply_body.index("await session.commit()")
    execute = apply_body.index("return await _execute_live_transition", durable_commit)
    assert durable_commit < execute

    execute_body = _function(source, "_execute_live_transition")
    group_lock = execute_body.index("select(Group).where(Group.id == group_id).with_for_update()")
    intent_lock = execute_body.index("select(ChatPermissionTransition)", group_lock)
    automatic_recheck = execute_body.index("_automatic_transition_is_current", intent_lock)
    telegram_effect = execute_body.index("await bot.set_chat_permissions", automatic_recheck)
    assert group_lock < intent_lock < automatic_recheck < telegram_effect


def test_automatic_recheck_covers_lockdown_and_night_conditions() -> None:
    source = (ROOT / "app/services/chat_permission_transitions.py").read_text(encoding="utf-8")
    helper = source.split("def _automatic_transition_is_current(", 1)[1].split("async def _finalize", 1)[0]
    assert 'intent.operation == "lockdown_off"' in helper
    assert "settings.lockdown_until <= now" in helper
    assert "settings.night_mode_enabled" in helper
    assert "is_night_window(" in helper
    assert 'intent.operation == "night_lock"' in helper
    assert 'intent.operation == "night_unlock"' in helper
    assert "not settings.lockdown_enabled" in helper


def test_permission_mode_owner_mutations_lock_before_authorization() -> None:
    source = (ROOT / "app/handlers/permission_modes.py").read_text(encoding="utf-8")
    helper = source.split("async def _owner_group(", 1)[1].split("async def _current_permissions", 1)[0]
    assert "for_update: bool = False" in helper
    assert ".with_for_update()" in helper
    assert helper.index(".with_for_update()") < helper.index("can_manage_group(")

    for name in ("safe_lockdown_on", "safe_lockdown_off", "safe_night_mode_off"):
        assert "for_update=True" in _function(source, name)


def test_permission_modes_router_is_production_winner_over_advanced() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    order = main.split("dp.include_routers(", 1)[1]
    permission_modes = order.index("\n        permission_modes.router,")
    advanced = order.index("\n        advanced.router,")
    assert permission_modes < advanced


def test_production_scheduler_reaches_permission_mode_workers() -> None:
    delivery = (ROOT / "app/tasks_delivery.py").read_text(encoding="utf-8")
    loop = delivery.split("async def background_loop(", 1)[1]
    assert "await expire_lockdowns(bot)" in loop
    assert "await apply_night_modes(bot)" in loop
