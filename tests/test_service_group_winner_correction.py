from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_real_service_group_callback_winner_uses_serialized_helper() -> None:
    main = _source("app/main.py")
    assert main.index("group_directory.router") < main.index("service_group_access.router")
    assert main.index("group_directory.router") < main.index("service_management.router")

    handler = _source("app/handlers/group_directory.py")
    body = handler.split("async def service_group_action", 1)[1]
    assert "await set_group_service_active(" in body
    assert 'active=action == "enable"' in body
    assert "result.blocked_owner" in body
    assert "group.is_active = action == \"enable\"" not in body
    assert "await session.commit()" not in body


def test_shared_service_group_helper_keeps_lock_and_blocked_owner_recheck() -> None:
    service = _source("app/services/client_access.py")
    body = service.split("async def set_group_service_active", 1)[1]
    assert ".with_for_update()" in body
    assert "select(User.service_blocked)" in body
    assert "if bool(blocked_owner):" in body
    assert "group.is_active = active" in body
    assert body.index(".with_for_update()") < body.index("select(User.service_blocked)")
    assert body.index("select(User.service_blocked)") < body.index("group.is_active = active")
    mutation = body.split("group.is_active = active", 1)[1]
    assert "await session.commit()" in mutation


def test_handler_contract_locks_group_directory_as_callback_winner() -> None:
    contract = _source("scripts/audit_handler_contracts.py")
    assert (
        '"F.data.regexp(\'^service_group_action:\\\\\\\\d+:(enable|disable)$\')": '
        '"group_directory.service_group_action"'
    ) in contract
