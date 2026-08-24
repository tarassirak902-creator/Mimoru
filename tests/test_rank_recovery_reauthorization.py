from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _recovery_body() -> str:
    source = (ROOT / "app/services/rank_provisioning.py").read_text(encoding="utf-8")
    return source.split("async def recover_rank_provisioning_intents", 1)[1]


def test_rank_recovery_reopens_candidates_under_group_then_intent_lock() -> None:
    body = _recovery_body()

    candidate_scan = body.index("select(RankProvisioningIntent.id)")
    group_id = body.index("select(RankProvisioningIntent.group_id)", candidate_scan)
    group_select = body.index("select(Group)", group_id)
    group_lock = body.index(".with_for_update()", group_select)
    intent_select = body.index("select(RankProvisioningIntent)", group_lock)
    intent_lock = body.index(".with_for_update()", intent_select)
    authority = body.index("_actor_can_recover_intent", intent_lock)
    telegram_lookup = body.index("await bot.get_chat_member", authority)

    assert candidate_scan < group_id < group_select < group_lock < intent_select < intent_lock < authority < telegram_lookup


def test_rank_recovery_reauthorizes_before_any_finalize() -> None:
    source = (ROOT / "app/services/rank_provisioning.py").read_text(encoding="utf-8")
    helper = source.split("async def _actor_can_recover_bot_only_intent", 1)[1].split(
        "async def _actor_can_recover_intent", 1
    )[0]
    body = _recovery_body()

    assert "can_assign_rank(" in helper
    assert "can_remove_assignment(" in helper
    authority = body.index("_actor_can_recover_intent")
    assert authority < body.index("await bot.get_chat_member", authority)
    assert authority < body.index("await _finalize_intent", authority)


def test_rank_recovery_never_replays_telegram_mutations() -> None:
    body = _recovery_body()
    assert "promote_chat_member(" not in body
    assert "demote_telegram_admin(" not in body
    assert "await bot.get_chat_member" in body


def test_rank_recovery_is_production_startup_path() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "from app.services.rank_provisioning import recover_rank_provisioning_intents" in main
    assert "await recover_rank_provisioning_intents(bot)" in main
