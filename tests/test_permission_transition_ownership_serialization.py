from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _service() -> str:
    return (ROOT / "app/services/chat_permission_transitions.py").read_text(encoding="utf-8")


def test_live_permission_execution_reauthorizes_under_group_lock() -> None:
    code = _service()
    start = code.index("async def _execute_live_transition")
    end = code.index("async def apply_permission_transition", start)
    body = code[start:end]

    group_lock = body.index("select(Group).where(Group.id == group_id).with_for_update()")
    intent_lock = body.index("select(ChatPermissionTransition)")
    actor_check = body.index("actor_id is not None and actor_id != group.owner_telegram_id")
    telegram = body.index("await bot.set_chat_permissions(group.telegram_chat_id, desired_permissions)")
    finalize = body.index("await _finalize(session, group, intent)")

    assert group_lock < intent_lock < actor_check < telegram < finalize
    assert "not is_service_owner(actor_id)" in body


def test_stale_manual_permission_actor_drops_intent_before_telegram() -> None:
    code = _service()
    start = code.index("if actor_id is not None and actor_id != group.owner_telegram_id")
    end = code.index("desired_permissions =", start)
    stale = code[start:end]

    assert "await session.delete(intent)" in stale
    assert "await session.commit()" in stale
    assert "set_chat_permissions" not in stale


def test_intent_is_durable_before_second_transaction_execution() -> None:
    code = _service()
    start = code.index("async def apply_permission_transition")
    end = code.index("async def recover_chat_permission_transitions", start)
    body = code[start:end]

    durable_commit = body.index("await session.commit()")
    execute = body.index("return await _execute_live_transition(")
    assert durable_commit < execute
    assert "actor_id=actor_id" in body
    assert "actor_id: int | None = None" in body


def test_manual_handlers_pass_actor_but_automatic_tasks_remain_system_owned() -> None:
    handlers = (ROOT / "app/handlers/permission_modes.py").read_text(encoding="utf-8")
    tasks = (ROOT / "app/tasks_permission_modes.py").read_text(encoding="utf-8")

    assert handlers.count("await apply_permission_transition(") == 3
    assert handlers.count("actor_id=message.from_user.id") == 3
    assert "message.from_user is None" in handlers
    assert tasks.count("await apply_permission_transition(") == 3
    assert "actor_id=" not in tasks


def test_recovery_remains_reconcile_only() -> None:
    code = _service()
    start = code.index("async def recover_chat_permission_transitions")
    body = code[start:]
    assert "permissions_match(chat.permissions, intent.desired_permissions)" in body
    assert "permissions_match(chat.permissions, intent.previous_permissions)" in body
    assert "set_chat_permissions" not in body
