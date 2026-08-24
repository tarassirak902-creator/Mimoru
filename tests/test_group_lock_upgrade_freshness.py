from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _function(source: str, name: str, next_name: str | None = None) -> str:
    start = source.index(f"async def {name}")
    if next_name is None:
        return source[start:]
    return source[start:source.index(f"async def {next_name}", start)]


def test_owner_management_refreshes_identity_when_upgrading_to_group_lock() -> None:
    source = (ROOT / "app/services/owner_management.py").read_text(encoding="utf-8")
    body = _function(source, "managed_group_for_message")

    unlocked = body.index("await get_or_create_group")
    lock = body.index(".with_for_update()", unlocked)
    refresh = body.index(".execution_options(populate_existing=True)", lock)
    authorize = body.index("await can_manage_group", refresh)

    assert unlocked < lock < refresh < authorize


def test_advanced_group_refreshes_identity_before_owner_or_rank_authorization() -> None:
    source = (ROOT / "app/handlers/advanced.py").read_text(encoding="utf-8")
    group = _function(source, "_group", "_owner_group")
    owner = _function(source, "_owner_group", "lockdown_on")

    unlocked = group.index("await get_or_create_group")
    lock = group.index(".with_for_update()", unlocked)
    refresh = group.index(".execution_options(populate_existing=True)", lock)
    assert unlocked < lock < refresh

    assert "group = await _group(message, session, for_update=for_update)" in owner
    assert "await can_manage_group" in owner


def test_mutating_advanced_paths_still_request_serialized_group() -> None:
    source = (ROOT / "app/handlers/advanced.py").read_text(encoding="utf-8")

    for name, next_name in (
        ("lockdown_on", "lockdown_off"),
        ("lockdown_off", "lockdown_status"),
        ("add_note", "list_notes"),
        ("delete_note", "set_timezone"),
        ("set_timezone", "show_timezone"),
        ("schedule_message", "schedule_list"),
        ("cancel_scheduled", "night_mode_on"),
        ("night_mode_on", "night_mode_off"),
        ("night_mode_off", "night_mode_status"),
    ):
        body = _function(source, name, next_name)
        assert "for_update=True" in body
