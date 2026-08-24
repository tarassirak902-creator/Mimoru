from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _recovery_body() -> str:
    source = (ROOT / "app/services/join_request_transitions.py").read_text(encoding="utf-8")
    return source.split("async def recover_join_request_reviews", 1)[1].split(
        "async def begin_invite_creation", 1
    )[0]


def test_join_review_recovery_scans_only_stale_processing_claims() -> None:
    source = (ROOT / "app/services/join_request_transitions.py").read_text(encoding="utf-8")
    body = _recovery_body()

    assert "JOIN_REVIEW_CLAIM_STALE_AFTER = timedelta(minutes=5)" in source
    assert "cutoff = datetime.now(timezone.utc) - JOIN_REVIEW_CLAIM_STALE_AFTER" in body
    assert "JoinRequestRecord.reviewed_at.is_(None)" in body
    assert "JoinRequestRecord.reviewed_at <= cutoff" in body
    assert "_join_review_claim_is_stale(row, datetime.now(timezone.utc))" in body


def test_join_review_recovery_serializes_group_then_request_before_readback() -> None:
    body = _recovery_body()

    group_id = body.index("select(JoinRequestRecord.group_id)")
    group_select = body.index("select(Group)", group_id)
    group_lock = body.index(".with_for_update()", group_select)
    request_select = body.index("select(JoinRequestRecord)", group_lock)
    request_lock = body.index(".with_for_update()", request_select)
    stale_recheck = body.index("_join_review_claim_is_stale", request_lock)
    telegram_readback = body.index("await bot.get_chat_member", stale_recheck)

    assert group_id < group_select < group_lock < request_select < request_lock
    assert request_lock < stale_recheck < telegram_readback


def test_join_review_recovery_remains_reconcile_only() -> None:
    body = _recovery_body()

    assert "await bot.get_chat_member" in body
    assert "approve_chat_join_request" not in body
    assert "decline_chat_join_request" not in body


def test_stale_join_review_recovery_runs_under_background_leader() -> None:
    leader = (ROOT / "app/services/background_leader.py").read_text(encoding="utf-8")
    periodic = leader.split("async def _recover_join_reviews_periodically", 1)[1].split(
        "async def _run_leader_worker", 1
    )[0]
    worker = leader.split("async def _run_leader_worker", 1)[1].split(
        "async def leader_background_loop", 1
    )[0]

    assert "await recover_join_request_reviews(bot)" in periodic
    assert "timeout=JOIN_REVIEW_RECOVERY_SECONDS" in periodic
    assert "_recover_join_reviews_periodically(bot, local_stop)" in worker
    assert 'name="join-review-recovery"' in worker
    assert "await stop_task(review_recovery" in worker


def test_join_review_recovery_and_safe_handler_are_production_reachable() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")

    assert "await recover_join_request_reviews(bot)" in main
    routers = main.split("dp.include_routers(", 1)[1].split(")", 1)[0]
    assert routers.index("join_review_guard.router") < routers.index("join_requests.router")
