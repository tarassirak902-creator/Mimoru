from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source() -> str:
    return (ROOT / "app/handlers/group_commands.py").read_text(encoding="utf-8")


def _handler(source: str, name: str) -> str:
    body = source.split(f"async def {name}(", 1)[1]
    return body.split("@router.", 1)[0]


def test_active_group_lock_is_opt_in() -> None:
    source = _source()
    helper = source.split("async def _active_group(", 1)[1].split("def _target_from_reply", 1)[0]
    assert "for_update: bool = False" in helper
    assert "if for_update:" in helper
    assert "query = query.with_for_update()" in helper


def test_clear_all_warnings_locks_before_live_authorization_and_commit() -> None:
    body = _handler(_source(), "clear_all_warnings")
    lock = body.index("await _active_group(session, message.chat.id, for_update=True)")
    permission = body.index("await can_moderate(")
    hierarchy = body.index("await can_moderate_target(")
    mutation = body.index("row.active = False")
    commit = body.index("await session.commit()")
    assert lock < permission < hierarchy < mutation < commit


def test_execute_based_moderation_handlers_do_not_take_outer_group_lock() -> None:
    source = _source()
    for name in ("direct_reply_moderation",):
        body = _handler(source, name)
        assert "for_update=True" not in body
        assert "await execute(" in body


def test_unmute_and_unban_combined_do_not_take_outer_group_lock() -> None:
    source = _source()
    for name in ("unmute_combined", "unban_combined"):
        body = _handler(source, name)
        assert "for_update=True" not in body
        assert "await execute(" in body or "_do_unmute(" in body or "_do_unban(" in body


def test_unmute_and_unban_helpers_do_not_take_outer_group_lock() -> None:
    source = _source()
    for name in ("_do_unmute", "_do_unban"):
        body = _handler(source, name)
        assert "for_update=True" not in body
        assert "await execute(" in body
