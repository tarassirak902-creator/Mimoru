from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source() -> str:
    return (ROOT / "app/handlers/features.py").read_text(encoding="utf-8")


def test_managed_can_lock_group_before_live_authorization() -> None:
    source = _source()
    helper = source.split("async def managed", 1)[1].split("@router.message", 1)[0]
    assert "for_update: bool = False" in helper
    assert ".with_for_update()" in helper
    assert helper.index(".with_for_update()") < helper.index("await can_manage_group(")


def test_mutating_feature_handlers_request_locked_management() -> None:
    source = _source()
    mutating = [
        "antiflood_config",
        "toggle_extended",
        "caps_limit",
        "welcome_text",
        "rules_text",
        "add_trigger",
        "remove_trigger",
    ]
    for name in mutating:
        body = source.split(f"async def {name}", 1)[1].split("@router.message", 1)[0]
        assert "await managed(message, bot, session, for_update=True)" in body
        assert body.index("for_update=True") < body.index("await session.commit()")


def test_read_only_trigger_list_remains_nonlocking() -> None:
    source = _source()
    body = source.split("async def list_triggers", 1)[1].split("@router.message", 1)[0]
    assert "await managed(message, bot, session)" in body
    assert "for_update=True" not in body


def test_public_handlers_do_not_use_owner_lock() -> None:
    source = _source()
    for signature in ("async def rules(", "async def complaint(", "async def statistics("):
        body = source.split(signature, 1)[1]
        assert "for_update=True" not in body.split("@router.message", 1)[0]
