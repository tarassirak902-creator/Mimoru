from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_client_blocking_locks_user_then_current_owned_groups() -> None:
    source = (ROOT / "app/services/client_access.py").read_text(encoding="utf-8")
    body = source.split("async def set_client_blocked", 1)[1]

    user_lock = body.index("select(User).where(User.telegram_id == telegram_id).with_for_update()")
    group_select = body.index("select(Group)")
    owner_filter = body.index("Group.owner_telegram_id == telegram_id")
    group_lock = body.index(".with_for_update()", group_select)
    deactivate = body.index("group.is_active = False")
    blocked_write = body.index("user.service_blocked = blocked")
    commit = body.index("await session.commit()")

    assert user_lock < group_select < owner_filter < group_lock < deactivate
    assert deactivate < blocked_write < commit


def test_unblock_does_not_reenable_groups() -> None:
    source = (ROOT / "app/services/client_access.py").read_text(encoding="utf-8")
    body = source.split("async def set_client_blocked", 1)[1]
    assert "if blocked:" in body
    assert "group.is_active = True" not in body


def test_modern_and_legacy_client_mutations_use_serialized_winners() -> None:
    source = (ROOT / "app/handlers/service_management_fixes.py").read_text(encoding="utf-8")
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")

    modern = source.split("async def client_action_serialized", 1)[1].split(
        "@router.message", 1
    )[0]
    legacy_block = source.split("async def legacy_block_client_serialized", 1)[1].split(
        "@router.message", 1
    )[0]
    legacy_unblock = source.split("async def legacy_unblock_client_serialized", 1)[1].split(
        "@router.message", 1
    )[0]

    assert 'F.data.regexp(r"^service_client_action:\\d+:(block|unblock)$")' in source
    assert 'F.text.regexp(r"(?i)^заблокировать клиента \\d+$")' in source
    assert 'F.text.regexp(r"(?i)^разблокировать клиента \\d+$")' in source
    assert "await set_client_blocked(" in modern
    assert "await set_client_blocked(" in legacy_block
    assert "await set_client_blocked(" in legacy_unblock
    assert "group.is_active = False" not in modern
    assert "group.is_active = False" not in legacy_block
    assert "user.service_blocked" not in modern
    assert "user.service_blocked" not in legacy_block

    fixes = main.index("service_management_fixes.router")
    assert fixes < main.index("service_management.router")
    assert fixes < main.index("client_management.router")
