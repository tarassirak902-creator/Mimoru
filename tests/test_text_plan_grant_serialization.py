from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_text_plan_syntax_is_intercepted_by_hardened_router() -> None:
    source = (ROOT / "app/handlers/service_management_fixes.py").read_text(encoding="utf-8")
    assert 'F.text.regexp(r"(?i)^выдать тариф \\d+ (free|standard|pro|trial) \\d+д$")' in source
    assert "async def grant_plan_serialized" in source
    handler = source.split("async def grant_plan_serialized", 1)[1].split(
        "@router.callback_query", 1
    )[0]
    assert "is_service_owner(message.from_user.id)" in handler
    assert "await apply_manual_plan(" in handler
    assert "session.get(Group" not in handler


def test_hardened_service_router_precedes_legacy_text_grant_router() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    fixes = main.index("service_management_fixes.router")
    legacy = main.index("service_admin.router")
    assert fixes < legacy


def test_text_and_callback_grants_share_the_same_locked_service() -> None:
    source = (ROOT / "app/handlers/service_management_fixes.py").read_text(encoding="utf-8")
    assert source.count("await apply_manual_plan(") >= 3
    service = (ROOT / "app/services/manual_plans.py").read_text(encoding="utf-8")
    helper = service.split("async def apply_manual_plan", 1)[1]
    assert ".with_for_update()" in helper
    assert "session.add(GroupSubscriptionEvent(" in helper
    assert "await session.commit()" in helper
