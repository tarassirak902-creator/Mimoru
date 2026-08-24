from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_audit_delivery_marks_ambiguity_before_telegram_send() -> None:
    source = (ROOT / "app/services/audit.py").read_text(encoding="utf-8")
    marker_fn = source[
        source.index("async def _mark_audit_delivery_uncertain"):
        source.index("async def _finalize_audit_delivery")
    ]
    deliver = source[source.index("async def deliver_pending_logs"):]

    assert "UNCERTAIN_DELIVERY_ERROR" in marker_fn
    marker = marker_fn.index("row.delivery_error = UNCERTAIN_DELIVERY_ERROR")
    commit = marker_fn.index("await session.commit()", marker)
    assert marker < commit

    claim_call = deliver.index("await _mark_audit_delivery_uncertain(row_id)")
    telegram = deliver.index("await bot.send_message", claim_call)
    finalize = deliver.index("await _finalize_audit_delivery(row_id)", telegram)
    assert claim_call < telegram < finalize


def test_audit_delivery_holds_live_group_gate_through_send_and_finalize() -> None:
    source = (ROOT / "app/services/audit.py").read_text(encoding="utf-8")
    deliver = source[source.index("async def deliver_pending_logs"):]

    group_lock = deliver.index(
        "select(Group).where(Group.id == group_id).with_for_update()"
    )
    destination_check = deliver.index("if group.settings.audit_chat_id is None:", group_lock)
    claim = deliver.index("await _mark_audit_delivery_uncertain(row_id)", destination_check)
    telegram = deliver.index("await bot.send_message", claim)
    finalize = deliver.index("await _finalize_audit_delivery(row_id)", telegram)
    release_group = deliver.index("await gate_session.commit()", finalize)

    assert group_lock < destination_check < claim < telegram < finalize < release_group


def test_only_definite_telegram_rejections_reenter_retry_budget() -> None:
    source = (ROOT / "app/services/audit.py").read_text(encoding="utf-8")
    deliver = source[source.index("async def deliver_pending_logs"):]
    release = source[
        source.index("async def _release_definite_audit_failure"):
        source.index("async def _finish_without_destination")
    ]

    assert "except (TelegramBadRequest, TelegramForbiddenError) as error:" in deliver
    assert "await _release_definite_audit_failure(" in deliver
    assert "except Exception" not in deliver
    assert "attempts_before_claim + 1" in release


def test_ambiguous_rows_are_not_selected_for_blind_retry() -> None:
    source = (ROOT / "app/services/audit.py").read_text(encoding="utf-8")
    assert "MAX_DELIVERY_ATTEMPTS = 5" in source
    marker_fn = source[
        source.index("async def _mark_audit_delivery_uncertain"):
        source.index("async def _finalize_audit_delivery")
    ]
    scan = source[source.index("async def deliver_pending_logs"):]

    assert "row.delivery_attempts = MAX_DELIVERY_ATTEMPTS" in marker_fn
    assert "ModerationLog.delivery_attempts < MAX_DELIVERY_ATTEMPTS" in scan
    assert "row.delivery_error != UNCERTAIN_DELIVERY_ERROR" in source
