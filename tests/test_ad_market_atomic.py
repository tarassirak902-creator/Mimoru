from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_atomic_ad_market_router_precedes_legacy_router():
    source = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "ad_market_atomic.router," in source
    assert source.index("ad_market_atomic.router,") < source.index("ad_market_v3.router,")


def test_global_review_and_deal_decision_lock_rows():
    source = (ROOT / "app/handlers/ad_market_atomic.py").read_text(encoding="utf-8")
    global_review = source.split("async def atomic_global_review", 1)[1].split("@router.message", 1)[0]
    deal_decision = source.split("async def atomic_required_deal_decision", 1)[1]
    assert ".with_for_update()" in global_review
    assert "item.status != \"pending_review\"" in global_review
    assert ".with_for_update()" in deal_decision
    assert "deal.status != \"pending\"" in deal_decision


def test_pending_deal_creation_serializes_on_listing():
    source = (ROOT / "app/handlers/ad_market_atomic.py").read_text(encoding="utf-8")
    target = source.split("async def atomic_required_deal_target", 1)[1].split("@router.callback_query", 1)[0]
    lock_pos = target.index(".with_for_update()")
    duplicate_pos = target.index("RequiredAdDealRequest.status == \"pending\"")
    insert_pos = target.index("deal = RequiredAdDealRequest(")
    commit_pos = target.index("await session.commit()")
    assert lock_pos < duplicate_pos < insert_pos < commit_pos


def test_atomic_callbacks_are_locked_as_duplicate_winners():
    audit = (ROOT / "scripts/audit_handler_contracts.py").read_text(encoding="utf-8")
    assert '"ad_market_atomic.atomic_global_review"' in audit
    assert '"ad_market_atomic.atomic_required_deal_decision"' in audit
