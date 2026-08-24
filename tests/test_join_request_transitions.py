from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_manual_join_review_claim_is_committed_before_telegram():
    service = (ROOT / "app/services/join_request_transitions.py").read_text(encoding="utf-8")
    claim = service.split("async def claim_join_review", 1)[1].split("async def finalize_join_review", 1)[0]
    assert ".with_for_update()" in claim
    assert 'JoinRequestRecord.status == "pending"' in claim
    assert "await session.commit()" in claim

    handler = (ROOT / "app/handlers/join_requests.py").read_text(encoding="utf-8")
    review = handler.split("async def review_request", 1)[1].split("@router.message", 1)[0]
    assert review.index("await claim_join_review") < review.index("await bot.approve_chat_join_request")


def test_auto_approve_persists_processing_state_before_telegram():
    source = (ROOT / "app/handlers/join_requests.py").read_text(encoding="utf-8")
    function = source.split("async def on_join_request", 1)[1].split("@router.chat_member", 1)[0]
    processing_pos = function.index("status=PROCESSING_APPROVE")
    commit_pos = function.index("await session.commit()")
    telegram_pos = function.index("await request.approve()")
    assert processing_pos < commit_pos < telegram_pos


def test_join_recovery_never_replays_approve_or_decline():
    source = (ROOT / "app/services/join_request_transitions.py").read_text(encoding="utf-8")
    recovery = source.split("async def recover_join_request_reviews", 1)[1].split(
        "async def begin_invite_creation", 1
    )[0]
    assert "await bot.get_chat_member" in recovery
    assert "approve_chat_join_request" not in recovery
    assert "decline_chat_join_request" not in recovery
    assert "REVIEW_UNCERTAIN" in recovery


def test_invite_create_ledger_precedes_external_creation():
    service = (ROOT / "app/services/join_request_transitions.py").read_text(encoding="utf-8")
    begin = service.split("async def begin_invite_creation", 1)[1].split(
        "async def finalize_invite_creation", 1
    )[0]
    assert 'status=CREATE_IN_PROGRESS' in begin
    assert "await session.commit()" in begin

    handler = (ROOT / "app/handlers/join_requests.py").read_text(encoding="utf-8")
    create = handler.split("async def create_invite", 1)[1].split("@router.message", 1)[0]
    assert create.index("await begin_invite_creation") < create.index("await bot.create_chat_invite_link")


def test_invite_revoke_ledger_precedes_external_revocation():
    handler = (ROOT / "app/handlers/join_requests.py").read_text(encoding="utf-8")
    disable = handler.split("async def disable_invite", 1)[1].split("@router.message", 1)[0]
    assert disable.index("await begin_invite_revocation") < disable.index("await bot.revoke_chat_invite_link")
    assert "mark_invite_revocation_uncertain" in disable
    assert "row.active = False" not in disable


def test_interrupted_invite_operations_are_quarantined_not_silently_dropped():
    source = (ROOT / "app/services/join_request_transitions.py").read_text(encoding="utf-8")
    recovery = source.split("async def recover_invite_operations", 1)[1]
    assert "CREATE_UNCERTAIN" in recovery
    assert "REVOKE_UNCERTAIN" in recovery
    assert "create_chat_invite_link" not in recovery
    assert "revoke_chat_invite_link" not in recovery


def test_startup_runs_join_and_invite_recovery():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "await recover_join_request_reviews(bot)" in main
    assert "await recover_invite_operations()" in main


def test_invite_operation_schema_is_registered():
    env = (ROOT / "alembic/env.py").read_text(encoding="utf-8")
    schema = (ROOT / "scripts/check_schema_consistency.py").read_text(encoding="utf-8")
    assert "invite_operation_models" in env
    assert "invite_operation_models" in schema
