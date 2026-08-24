from pathlib import Path


SOURCE = Path("app/tasks_ad_market.py").read_text(encoding="utf-8")


def _function_source(name: str) -> str:
    marker = f"async def {name}("
    start = SOURCE.index(marker)
    next_start = SOURCE.find("\n\nasync def ", start + len(marker))
    return SOURCE[start:] if next_start == -1 else SOURCE[start:next_start]


def test_delivery_claim_is_committed_before_telegram_send() -> None:
    claim = _function_source("_claim_delivery")
    publish = _function_source("_publish_global_request")

    assert 'status="claimed"' in claim
    assert claim.index("session.add(claim)") < claim.index("await session.commit()")
    claim_call = publish.index("claim = await _claim_delivery")
    first_send = min(
        index for index in (
            publish.find("await bot.send_photo", claim_call),
            publish.find("await bot.send_message", claim_call),
        )
        if index != -1
    )
    assert claim_call < first_send


def test_duplicate_claim_only_suppresses_confirmed_existing_delivery() -> None:
    claim = _function_source("_claim_delivery")

    rollback = claim.index("await session.rollback()")
    reread = claim.index("existing = await session.scalar", rollback)
    duplicate_return = claim.index("return None", reread)
    reraised = claim.index("raise", duplicate_return)

    assert rollback < reread < duplicate_return < reraised
    assert "GlobalPostDelivery.request_id == request_id" in claim
    assert "GlobalPostDelivery.group_id == group_id" in claim


def test_stale_claimed_rows_are_released_but_processing_is_quarantined() -> None:
    recovery = _function_source("_recover_stale_delivery_claims")
    publish = _function_source("_publish_global_request")

    delete_claimed = recovery.index("delete(GlobalPostDelivery)")
    claimed_guard = recovery.index('GlobalPostDelivery.status == "claimed"', delete_claimed)
    processing_guard = recovery.index('GlobalPostDelivery.status == "processing"', claimed_guard)
    failed = recovery.index('row.status = "failed"', processing_guard)

    assert delete_claimed < claimed_guard < processing_guard < failed
    assert "DELIVERY_CLAIM_STALE_AFTER" in recovery
    assert "UNCERTAIN_DELIVERY_ERROR" in recovery
    assert publish.index("_recover_stale_delivery_claims") < publish.index("pending_group_ids =")


def test_processing_transition_is_durable_after_group_lock_before_send() -> None:
    marker = _function_source("_mark_delivery_processing")
    publish = _function_source("_publish_global_request")

    assert "async with SessionFactory() as marker_session:" in marker
    assert 'GlobalPostDelivery.status == "claimed"' in marker
    assert '.values(status="processing", delivered_at=func.now())' in marker
    assert marker.index("await marker_session.commit()") < marker.index("return transitioned")

    group_lock = publish.index("with_for_update()")
    transition = publish.index("await _mark_delivery_processing(claim.id)", group_lock)
    first_send = min(
        index for index in (
            publish.find("await bot.send_photo", transition),
            publish.find("await bot.send_message", transition),
        )
        if index != -1
    )
    final_commit = publish.index("await session.commit()", first_send)
    assert group_lock < transition < first_send < final_commit


def test_request_completion_waits_for_claimed_and_processing_deliveries() -> None:
    finalize = _function_source("_finalize_request_if_complete")

    assert 'row.status in {"claimed", "processing"}' in finalize
    assert "pending_group_ids" in finalize
    assert "or pending_group_ids" in finalize


def test_request_completion_is_claimed_before_buyer_notification() -> None:
    finalize = _function_source("_finalize_request_if_complete")

    conditional_update = finalize.index("update(GlobalPostRequest)")
    paid_guard = finalize.index('GlobalPostRequest.status == "paid"', conditional_update)
    commit = finalize.index("await session.commit()", paid_guard)
    notify = finalize.index("await bot.send_message", commit)

    assert conditional_update < paid_guard < commit < notify
    assert "if claimed_completion is None:" in finalize
