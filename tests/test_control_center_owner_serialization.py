from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _handler(source: str, name: str) -> str:
    body = source.split(f"async def {name}(", 1)[1]
    boundaries = [
        index
        for marker in ("\n@router.", "\nasync def ")
        if (index := body.find(marker)) >= 0
    ]
    return body[: min(boundaries)] if boundaries else body


def test_control_center_owner_lock_is_opt_in() -> None:
    source = (ROOT / "app/handlers/control_center.py").read_text(encoding="utf-8")
    helper = source.split("async def owned_group(", 1)[1].split("async def moderator_row", 1)[0]
    assert "for_update: bool = False" in helper
    assert "if for_update:" in helper
    assert "query = query.with_for_update()" in helper


def test_unique_content_and_setting_writes_lock_group() -> None:
    source = (ROOT / "app/handlers/control_center.py").read_text(encoding="utf-8")
    mutations = {
        "word_add_text": "session.add(ForbiddenWord(",
        "word_remove": "await session.delete(rows[index])",
        "channel_add_text": "session.add(RequiredChannel(",
        "channel_remove": "rows[index].active = False",
        "_save_setting_text": "group.settings.welcome_text = value",
        "setting_set": "group.settings.warnings_limit = value",
    }
    for name, mutation in mutations.items():
        body = _handler(source, name)
        lock = body.index("for_update=True")
        write = body.index(mutation)
        commit = body.index("await session.commit()")
        assert lock < write < commit


def test_navigation_and_shadowed_setters_remain_non_locking() -> None:
    source = (ROOT / "app/handlers/control_center.py").read_text(encoding="utf-8")
    for name in ("word_add", "channel_add", "settings_detail", "setting_text", "setting_num", "setting_flood"):
        assert "for_update=True" not in _handler(source, name)


def test_router_precedence_defines_production_winners() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    order = main.split("dp.include_routers(", 1)[1]
    navigation = order.index("\n        navigation_fixes.router,")
    rank_guard = order.index("\n        rank_legacy_guard.router,")
    control = order.index("\n        control_center.router,")
    panel = order.index("\n        panel.router,")
    assert navigation < control < panel
    assert rank_guard < control

    navigation_source = (ROOT / "app/handlers/navigation_fixes.py").read_text(encoding="utf-8")
    assert 'F.data.regexp(r"^setting_set:\\d+:defaultmute:\\d+$")' in navigation_source
    assert 'F.data.regexp(r"^setting_flood:\\d+:(4|6|8):(5|10|15)$")' in navigation_source

    guard_source = (ROOT / "app/handlers/rank_legacy_guard.py").read_text(encoding="utf-8")
    assert 'F.data.regexp(r"^role_(add|edit|set|perm|reset|toggle|remove|remove_confirm):\\d+(?::.*)?$")' in guard_source
