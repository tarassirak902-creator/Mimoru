from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_plan_grant_uses_serialized_winner() -> None:
    source = (ROOT / "app/handlers/service_management_fixes.py").read_text(encoding="utf-8")
    handler = source.split("async def service_plan_grant_serialized", 1)[1].split(
        "async def service_plan_apply_serialized", 1
    )[0]
    assert "await _apply_manual_plan(" in handler
    assert "session.get(Group" not in handler
    assert "group.plan_expires_at =" not in handler


def test_dashboard_plan_grant_winner_is_locked_in_handler_audit() -> None:
    audit = (ROOT / "scripts/audit_handler_contracts.py").read_text(encoding="utf-8")
    assert "service_management_fixes.service_plan_grant_serialized" in audit
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert main.index("service_management_fixes.router") < main.index("dashboard.router")
