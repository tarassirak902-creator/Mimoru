from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source() -> str:
    return (ROOT / "app/handlers/required_direct.py").read_text(encoding="utf-8")


def _body(source: str, name: str) -> str:
    return source.split(f"async def {name}(", 1)[1].split("@router.", 1)[0]


def test_direct_required_mutations_use_locked_owner_boundary() -> None:
    source = _source()
    assert "managed_group_for_message" in source
    for name in ("direct_required_connect", "direct_required_disconnect"):
        body = _body(source, name)
        assert "for_update=True" in body
        assert body.index("for_update=True") < body.index("await session.commit()")


def test_plan_limit_is_checked_after_locked_owner_lookup() -> None:
    source = _source()
    body = _body(source, "direct_required_connect")
    assert body.index("for_update=True") < body.index("plan_limit(group, \"channels\")")


def test_member_counter_locks_group_before_rule_rows() -> None:
    source = _source()
    body = source.split("async def count_direct_required_members(", 1)[1]
    group_select = body.index("select(Group)")
    active_group = body.index("Group.is_active.is_(True)", group_select)
    group_lock = body.index(".with_for_update()", active_group)
    rule_select = body.index("select(DirectRequiredRule)", group_lock)
    active_rule = body.index("DirectRequiredRule.active.is_(True)", rule_select)
    rule_lock = body.index(".with_for_update()", active_rule)
    mutation = body.index("rule.used_count += 1", rule_lock)
    commit = body.index("await session.commit()", mutation)
    assert group_select < active_group < group_lock < rule_select < active_rule < rule_lock < mutation < commit


def test_member_counter_is_registered_for_user_chat_member_updates() -> None:
    source = _source()
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    onboarding = (ROOT / "app/handlers/group_onboarding_flow.py").read_text(encoding="utf-8")

    assert "@router.chat_member()\nasync def count_direct_required_members" in source
    assert "required_direct.router" in main
    assert "@router.my_chat_member()\nasync def bot_group_membership_changed" in onboarding
