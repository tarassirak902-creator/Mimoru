from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_group_activation_locks_group_before_blocked_owner_recheck() -> None:
    source = (ROOT / "app/services/client_access.py").read_text(encoding="utf-8")
    body = source.split("async def set_group_service_active(", 1)[1]

    group_lock = body.index("select(Group).where(Group.id == group_id).with_for_update()")
    owner_guard = body.index("if active and group.owner_telegram_id is not None:", group_lock)
    blocked_read = body.index("select(User.service_blocked)", owner_guard)
    owner_filter = body.index("User.telegram_id == group.owner_telegram_id", blocked_read)
    blocked_guard = body.index("if bool(blocked_owner):", owner_filter)
    blocked_commit = body.index("await session.commit()", blocked_guard)
    blocked_return = body.index("blocked_owner=True", blocked_commit)
    mutation = body.index("group.is_active = active", blocked_return)
    commit = body.index("await session.commit()", mutation)

    assert group_lock < owner_guard < blocked_read < owner_filter < blocked_guard
    assert blocked_guard < blocked_commit < blocked_return < mutation < commit
    # Avoid User -> Group / Group -> User deadlock inversion with set_client_blocked().
    assert "select(User).where(User.telegram_id == group.owner_telegram_id).with_for_update()" not in body


def test_client_block_still_serializes_owned_groups() -> None:
    source = (ROOT / "app/services/client_access.py").read_text(encoding="utf-8")
    body = source.split("async def set_client_blocked(", 1)[1].split(
        "async def set_group_service_active(", 1
    )[0]
    user_lock = body.index("select(User).where(User.telegram_id == telegram_id).with_for_update()")
    group_query = body.index("select(Group)", user_lock)
    group_lock = body.index(".with_for_update()", group_query)
    deactivate = body.index("group.is_active = False", group_lock)
    commit = body.index("await session.commit()", deactivate)
    assert user_lock < group_query < group_lock < deactivate < commit


def test_callback_group_action_uses_serialized_earlier_winner() -> None:
    source = (ROOT / "app/handlers/service_group_access.py").read_text(encoding="utf-8")
    assert 'F.data.regexp(r"^service_group_action:\\d+:(enable|disable)$")' in source
    body = source.split("async def group_action_serialized", 1)[1]
    assert "await set_group_service_active(" in body
    assert 'active=action == "enable"' in body
    assert "if result.blocked_owner:" in body
    assert "Сначала разблокируйте клиента-владельца группы." in body

    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    include = main.split("dp.include_routers(", 1)[1]
    assert include.index("service_group_access.router") < include.index("service_management.router")


def test_text_group_enable_uses_same_serialized_service() -> None:
    source = (ROOT / "app/handlers/client_management.py").read_text(encoding="utf-8")
    body = source.split("async def enable_group(", 1)[1].split("@router.message", 1)[0]
    assert "await set_group_service_active(" in body
    assert "active=True" in body
    assert "if result.blocked_owner:" in body
    assert "Сначала разблокируйте клиента-владельца группы." in body
    assert "group.is_active = True" not in body


def test_disable_remains_supported_by_shared_service() -> None:
    callback = (ROOT / "app/handlers/service_group_access.py").read_text(encoding="utf-8")
    assert 'active=action == "enable"' in callback
    service = (ROOT / "app/services/client_access.py").read_text(encoding="utf-8")
    body = service.split("async def set_group_service_active(", 1)[1]
    assert "if active and group.owner_telegram_id is not None:" in body
    assert "group.is_active = active" in body
