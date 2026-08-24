from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _decision_source() -> str:
    source = (ROOT / "app/handlers/ad_market_atomic.py").read_text(encoding="utf-8")
    return source.split("async def atomic_required_deal_decision", 1)[1]


def test_atomic_router_is_production_reqdeal_winner() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    include = main.split("dp.include_routers(", 1)[1].split(")", 1)[0]
    assert include.index("ad_market_atomic.router") < include.index("ad_market_v3.router")

    contracts = (ROOT / "scripts/audit_handler_contracts.py").read_text(encoding="utf-8")
    assert "^reqdeal:(accept|reject):" in contracts
    assert "ad_market_atomic.atomic_required_deal_decision" in contracts


def test_reqdeal_decision_uses_transfer_lock_order() -> None:
    function = _decision_source()
    snapshot = function.index("snapshot = await session.execute")
    group_lock = function.index("select(Group)")
    owner_check = function.index("Group.owner_telegram_id == callback.from_user.id")
    group_for_update = function.index(".with_for_update()", group_lock)
    listing_lock = function.index("select(RequiredAdListing)", group_lock)
    listing_for_update = function.index(".with_for_update()", listing_lock)
    deal_lock = function.index("select(RequiredAdDealRequest)", listing_lock)
    deal_for_update = function.index(".with_for_update()", deal_lock)
    pending_check = function.index('deal.status != "pending"')
    mutation = function.index('deal.status = "accepted" if accepted else "rejected"')
    commit = function.rindex("await session.commit()")

    assert (
        snapshot
        < group_lock
        < owner_check
        < group_for_update
        < listing_lock
        < listing_for_update
        < deal_lock
        < deal_for_update
        < pending_check
        < mutation
        < commit
    )


def test_reqdeal_decision_reauthorizes_every_marketplace_snapshot() -> None:
    function = _decision_source()
    assert "RequiredAdDealRequest.listing_id == listing.id" in function
    assert "RequiredAdListing.seller_group_id == group.id" in function
    assert "listing.seller_owner_telegram_id != callback.from_user.id" in function
    assert "deal.seller_telegram_id != callback.from_user.id" in function
    assert "Group.is_active.is_(True)" in function


def test_reqdeal_decision_does_not_lock_deal_before_group() -> None:
    function = _decision_source()
    pre_group = function.split("group = await session.scalar", 1)[0]
    assert "select(RequiredAdDealRequest).where" not in pre_group
    assert ".with_for_update()" not in pre_group
