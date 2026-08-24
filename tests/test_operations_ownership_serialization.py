from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source() -> str:
    return (ROOT / "app/handlers/operations.py").read_text(encoding="utf-8")


def test_managed_can_lock_group_before_live_authorization() -> None:
    source = _source()
    helper = source.split("async def _managed", 1)[1].split("@router.message", 1)[0]
    assert "for_update: bool = False" in helper
    assert ".with_for_update()" in helper
    assert helper.index(".with_for_update()") < helper.index("await can_manage_group(")


def test_mutating_operations_use_locked_management() -> None:
    source = _source()
    for name in ("import_settings", "toggle_reports", "report_hour"):
        body = source.split(f"async def {name}", 1)[1].split("@router.message", 1)[0]
        assert "await _managed(message, bot, session, for_update=True)" in body
        assert body.index("for_update=True") < body.index("await session.commit()")


def test_read_only_operations_remain_nonlocking() -> None:
    source = _source()
    for name in ("export_settings", "diagnostics"):
        body = source.split(f"async def {name}", 1)[1]
        if "@router.message" in body:
            body = body.split("@router.message", 1)[0]
        assert "await _managed(message, bot, session)" in body
        assert "for_update=True" not in body
