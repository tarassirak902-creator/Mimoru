import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "app/handlers/client_management.py"

DIRECT_COMMIT_HANDLERS = {"create_promo", "redeem_promo"}
SHADOWED_MUTATION_HANDLERS = {
    "disable_promo",
    "block_client",
    "unblock_client",
    "grant_trial",
}
READ_HANDLERS = {"list_promos", "clients", "extended_stats"}


def _handler_sources() -> dict[str, str]:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    result: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            segment = ast.get_source_segment(source, node)
            if segment is not None:
                result[node.name] = segment
    return result


def test_direct_client_management_mutations_commit_before_success_ack() -> None:
    handlers = _handler_sources()
    for name in DIRECT_COMMIT_HANDLERS:
        body = handlers[name]
        commit = body.rfind("await session.commit()")
        success = body.find("✅")
        assert commit != -1, f"{name} must explicitly commit its durable mutation"
        assert success != -1, f"{name} regression expects an explicit success acknowledgement"
        assert commit < success, f"{name} must commit before telling Telegram the mutation succeeded"


def test_enable_group_delegates_to_service_that_commits_before_returning() -> None:
    handlers = _handler_sources()
    body = handlers["enable_group"]
    call = body.index("await set_group_service_active(")
    blocked_guard = body.index("if result.blocked_owner:", call)
    success = body.index("✅", blocked_guard)
    assert call < blocked_guard < success
    assert "await session.commit()" not in body

    service = (ROOT / "app/services/client_access.py").read_text(encoding="utf-8")
    helper = service.split("async def set_group_service_active(", 1)[1]
    mutation = helper.index("group.is_active = active")
    commit = helper.index("await session.commit()", mutation)
    result = helper.index("return GroupServiceResult(group=group)", commit)
    assert mutation < commit < result


def test_shadowed_client_management_mutations_are_not_treated_as_winners() -> None:
    handlers = _handler_sources()
    for name in SHADOWED_MUTATION_HANDLERS:
        assert "await session.commit()" not in handlers[name]

    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    include = main.split("dp.include_routers(", 1)[1]
    assert include.index("service_management_fixes.router") < include.index("client_management.router")

    fixes = (ROOT / "app/handlers/service_management_fixes.py").read_text(encoding="utf-8")
    for command in (
        "отключить промокод",
        "заблокировать клиента",
        "разблокировать клиента",
        "тестовый период",
    ):
        assert command in fixes
    assert "await session.commit()" in fixes


def test_read_only_client_management_handlers_do_not_gain_commits() -> None:
    handlers = _handler_sources()
    for name in READ_HANDLERS:
        assert "await session.commit()" not in handlers[name]


def test_client_management_router_is_registered_in_production() -> None:
    source = (ROOT / "app/main.py").read_text(encoding="utf-8")
    include = source.split("dp.include_routers(", 1)[1]
    assert "client_management.router" in include


def test_shadowed_disable_group_command_stays_with_earlier_service_admin_winner() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    include = main.split("dp.include_routers(", 1)[1]
    assert include.index("service_admin.router") < include.index("client_management.router")

    service_admin = (ROOT / "app/handlers/service_admin.py").read_text(encoding="utf-8")
    assert "отключить группу" in service_admin
    assert "await session.commit()" in service_admin.split("async def disable_group(", 1)[1]
