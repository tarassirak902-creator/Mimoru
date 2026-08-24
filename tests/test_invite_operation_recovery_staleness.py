from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _recovery_body() -> str:
    source = (ROOT / "app/services/join_request_transitions.py").read_text(encoding="utf-8")
    return source.split("async def recover_invite_operations", 1)[1]


def test_invite_recovery_scans_only_stale_in_progress_operations() -> None:
    source = (ROOT / "app/services/join_request_transitions.py").read_text(encoding="utf-8")
    body = _recovery_body()

    assert "INVITE_OPERATION_STALE_AFTER = timedelta(minutes=5)" in source
    assert "func.coalesce(InviteOperation.updated_at, InviteOperation.created_at)" in body
    assert "freshness <= cutoff" in body
    assert "_invite_operation_is_stale(operation, datetime.now(timezone.utc))" in body


def test_invite_recovery_serializes_group_then_operation_and_rechecks_freshness() -> None:
    body = _recovery_body()

    group_id = body.index("select(InviteOperation.group_id)")
    group_select = body.index("select(Group)", group_id)
    group_lock = body.index(".with_for_update()", group_select)
    operation_select = body.index("select(InviteOperation)", group_lock)
    operation_lock = body.index(".with_for_update()", operation_select)
    stale_recheck = body.index("_invite_operation_is_stale", operation_lock)
    quarantine = body.index("operation.status = CREATE_UNCERTAIN", stale_recheck)
    commit = body.index("await session.commit()", quarantine)

    assert group_id < group_select < group_lock < operation_select < operation_lock
    assert operation_lock < stale_recheck < quarantine < commit


def test_invite_recovery_never_replays_telegram_create_or_revoke() -> None:
    body = _recovery_body()

    assert "create_chat_invite_link" not in body
    assert "revoke_chat_invite_link" not in body
    assert "CREATE_UNCERTAIN" in body
    assert "REVOKE_UNCERTAIN" in body


def test_stale_invite_recovery_runs_only_under_background_leader_worker() -> None:
    leader = (ROOT / "app/services/background_leader.py").read_text(encoding="utf-8")
    periodic = leader.split("async def _recover_invite_operations_periodically", 1)[1].split(
        "async def _run_leader_worker", 1
    )[0]
    worker = leader.split("async def _run_leader_worker", 1)[1].split(
        "async def leader_background_loop", 1
    )[0]

    assert "await recover_invite_operations()" in periodic
    assert "timeout=INVITE_OPERATION_RECOVERY_SECONDS" in periodic
    assert "_recover_invite_operations_periodically(local_stop)" in worker
    assert 'name="invite-operation-recovery"' in worker
    assert "await stop_task(invite_recovery" in worker


def test_invite_recovery_and_guard_router_are_production_reachable() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")

    assert "await recover_invite_operations()" in main
    routers = main.split("dp.include_routers(", 1)[1].split(")", 1)[0]
    assert routers.index("invite_operation_guard.router") < routers.index("join_requests.router")
