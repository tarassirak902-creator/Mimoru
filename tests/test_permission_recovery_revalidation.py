from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _recovery_body() -> str:
    source = (ROOT / "app/services/chat_permission_transitions.py").read_text(encoding="utf-8")
    return source.split("async def recover_chat_permission_transitions", 1)[1]


def test_permission_recovery_uses_group_then_intent_lock() -> None:
    body = _recovery_body()

    candidate_scan = body.index("select(ChatPermissionTransition.id)")
    group_id = body.index("select(ChatPermissionTransition.group_id)", candidate_scan)
    group_select = body.index("select(Group)", group_id)
    group_lock = body.index(".with_for_update()", group_select)
    intent_select = body.index("select(ChatPermissionTransition)", group_lock)
    intent_lock = body.index(".with_for_update()", intent_select)
    current_check = body.index("_automatic_transition_is_current", intent_lock)
    telegram_read = body.index("await bot.get_chat", current_check)

    assert candidate_scan < group_id < group_select < group_lock < intent_select < intent_lock
    assert intent_lock < current_check < telegram_read


def test_permission_recovery_revalidates_before_finalize_and_never_replays() -> None:
    body = _recovery_body()

    current_check = body.index("_automatic_transition_is_current")
    desired_match = body.index("permissions_match(chat.permissions, intent.desired_permissions)", current_check)
    finalize = body.index("await _finalize", desired_match)

    assert current_check < desired_match < finalize
    assert "set_chat_permissions(" not in body


def test_permission_recovery_is_startup_path_and_safe_router_is_winner() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")

    assert "from app.services.chat_permission_transitions import recover_chat_permission_transitions" in main
    assert "await recover_chat_permission_transitions(bot)" in main

    routers = main.split("dp.include_routers(", 1)[1].split(")", 1)[0]
    assert routers.index("permission_modes.router") < routers.index("advanced.router")
