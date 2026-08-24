from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source() -> str:
    return (ROOT / "app/handlers/advanced.py").read_text(encoding="utf-8")


def _body(source: str, name: str) -> str:
    return source.split(f"async def {name}(", 1)[1].split("@router.message", 1)[0]


def test_group_lock_precedes_owner_or_moderator_authorization() -> None:
    source = _source()
    group_helper = source.split("async def _group", 1)[1].split("async def _owner_group", 1)[0]
    owner_helper = source.split("async def _owner_group", 1)[1].split("@router.message", 1)[0]
    assert "for_update: bool = False" in group_helper
    assert ".with_for_update()" in group_helper
    assert "for_update=for_update" in owner_helper
    assert owner_helper.index("for_update=for_update") < owner_helper.index("await can_manage_group(")


def test_owner_mutations_use_locked_group() -> None:
    source = _source()
    for name in ("set_timezone", "schedule_message", "cancel_scheduled", "night_mode_on"):
        body = _body(source, name)
        assert "_owner_group(message, bot, session, for_update=True)" in body
        assert body.index("for_update=True") < body.index("await session.commit()")


def test_note_mutations_lock_before_live_moderation_check() -> None:
    source = _source()
    for name in ("add_note", "delete_note"):
        body = _body(source, name)
        assert "_group(message, session, for_update=True)" in body
        assert body.index("for_update=True") < body.index("await can_moderate(")
        assert body.index("await can_moderate(") < body.index("await session.commit()")


def test_read_only_advanced_paths_remain_nonlocking() -> None:
    source = _source()
    for name in ("list_notes", "show_timezone", "schedule_list", "night_mode_status"):
        body = _body(source, name)
        assert "for_update=True" not in body


def test_safe_permission_mode_router_still_precedes_advanced() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert main.index("permission_modes.router") < main.index("advanced.router")
