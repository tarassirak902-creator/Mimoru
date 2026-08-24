from pathlib import Path


HANDLER = Path("app/handlers/service_broadcast.py").read_text(encoding="utf-8")
MODELS = Path("app/db/broadcast_models.py").read_text(encoding="utf-8")
MIGRATION = Path("alembic/versions/0039_broadcast_delivery_claims.py").read_text(encoding="utf-8")


def _function_source(name: str) -> str:
    marker = f"async def {name}("
    start = HANDLER.index(marker)
    next_start = HANDLER.find("\n\nasync def ", start + len(marker))
    return HANDLER[start:] if next_start == -1 else HANDLER[start:next_start]


def test_broadcast_execution_is_durable_before_network_delivery() -> None:
    create = _function_source("_get_or_create_broadcast")
    send = _function_source("send_broadcast")

    assert "BroadcastExecution(" in create
    assert "payload=payload" in create
    assert create.index("await session.commit()") < create.index("except IntegrityError")
    assert send.index("_get_or_create_broadcast") < send.index("_send_composed")


def test_each_group_is_claimed_before_telegram_send() -> None:
    claim = _function_source("_claim_delivery")
    send = _function_source("send_broadcast")

    assert "BroadcastDelivery(" in claim
    assert claim.index("session.add(claim)") < claim.index("await session.commit()")
    claim_call = send.index("claim = await _claim_delivery")
    telegram_send = send.index("await _send_composed", claim_call)
    assert claim_call < telegram_send


def test_duplicate_claims_verify_canonical_row_before_suppression() -> None:
    claim = _function_source("_claim_delivery")

    rollback = claim.index("await session.rollback()")
    reread = claim.index("existing = await session.scalar", rollback)
    duplicate_return = claim.index("return None", reread)
    reraised = claim.index("raise", duplicate_return)
    assert rollback < reread < duplicate_return < reraised


def test_stale_ambiguous_deliveries_are_quarantined_not_retried() -> None:
    quarantine = _function_source("_quarantine_stale_deliveries")

    assert 'BroadcastDelivery.status == "processing"' in quarantine
    assert "DELIVERY_CLAIM_STALE_AFTER" in quarantine
    assert 'row.status = "failed"' in quarantine
    assert "UNCERTAIN_DELIVERY_ERROR" in quarantine


def test_schema_has_execution_payload_and_per_group_uniqueness() -> None:
    assert "class BroadcastExecution" in MODELS
    assert "payload: Mapped[dict]" in MODELS
    assert "class BroadcastDelivery" in MODELS
    assert 'UniqueConstraint("broadcast_id", "group_id"' in MODELS

    assert 'revision = "0039_broadcast_delivery_claims"' in MIGRATION
    assert 'down_revision = "0038_pending_bans"' in MIGRATION
    assert '"broadcast_executions"' in MIGRATION
    assert 'sa.Column("payload", sa.JSON(), nullable=False)' in MIGRATION
    assert '"broadcast_deliveries"' in MIGRATION
