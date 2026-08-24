from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_setup_mutation_locks_group_before_authorization_and_commit() -> None:
    source = (ROOT / "app/services/setup_mutations.py").read_text(encoding="utf-8")
    body = source.split("async def mutate_setup_group", 1)[1]

    group_lock = body.index(".with_for_update()")
    actor_check = body.index("actor_id != group.owner_telegram_id")
    mutation = body.index("result = mutation(group)")
    commit = body.index("await session.commit()")

    assert group_lock < actor_check < mutation < commit
    assert "not is_service_owner(actor_id)" in body


def test_all_mutating_setup_callbacks_use_locked_boundary() -> None:
    source = (ROOT / "app/handlers/onboarding.py").read_text(encoding="utf-8")
    assert source.count("await mutate_setup_group(") == 5

    for name in (
        "setup_level",
        "setup_captcha",
        "setup_welcome",
        "setup_quarantine",
        "setup_reports",
    ):
        start = source.index(f"async def {name}")
        next_handler = source.find("@router.callback_query", start)
        body = source[start:] if next_handler == -1 else source[start:next_handler]
        assert "await mutate_setup_group(" in body
        assert "await session.commit()" not in body


def test_setup_level_applies_profile_inside_locked_mutation() -> None:
    source = (ROOT / "app/handlers/onboarding.py").read_text(encoding="utf-8")
    start = source.index("async def setup_level")
    end = source.index("async def setup_captcha", start)
    body = source[start:end]

    assert "def apply_profile(group: Group)" in body
    assert "apply_setup_profile(group.settings, profile, level)" in body
    assert "mutation=apply_profile" in body


def test_reports_feature_gate_is_evaluated_inside_locked_mutation() -> None:
    source = (ROOT / "app/handlers/onboarding.py").read_text(encoding="utf-8")
    start = source.index("async def setup_reports")
    end = source.index("async def group_health", start)
    body = source[start:end]

    gate = body.index('reports_available = feature_available(group, "daily_reports")')
    mutate_call = body.index("await mutate_setup_group(")
    assert gate < mutate_call
    assert "mutation=set_reports" in body


def test_onboarding_router_remains_live_setup_owner() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    flow = (ROOT / "app/handlers/group_onboarding_flow.py").read_text(encoding="utf-8")
    onboarding = (ROOT / "app/handlers/onboarding.py").read_text(encoding="utf-8")

    assert "onboarding.router," in main
    assert 'callback_data=f"setup:{group_id}:start"' in flow
    assert '@router.callback_query(F.data.regexp(r"^setup:\\d+:level:' in onboarding
    assert '@router.callback_query(F.data.regexp(r"^setup:\\d+:reports:' in onboarding
