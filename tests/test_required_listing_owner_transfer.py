from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source() -> str:
    return (ROOT / "app/services/repositories.py").read_text(encoding="utf-8")


def test_owner_transfer_invalidates_listing_and_pending_deals_before_assignment() -> None:
    source = _source()
    helper = source.split("async def _invalidate_marketplace_on_owner_change", 1)[1].split(
        "async def get_or_create_group", 1
    )[0]
    group_lock = helper.index("select(Group).where(Group.id == group.id).with_for_update()")
    listing_lock = helper.index("select(RequiredAdListing)")
    deactivate = helper.index("listing.active = False")
    cancel = helper.index('deal.status = "cancelled"')
    assign = helper.index("group.owner_telegram_id = new_owner_id")
    assert group_lock < listing_lock < deactivate < cancel < assign
    assert 'RequiredAdDealRequest.status == "pending"' in helper
    assert "deal.decided_at = now" in helper


def test_same_owner_does_not_retire_marketplace_state() -> None:
    source = _source()
    helper = source.split("async def _invalidate_marketplace_on_owner_change", 1)[1].split(
        "async def get_or_create_group", 1
    )[0]
    assert "if group.owner_telegram_id == new_owner_id:" in helper
    assert "return" in helper.split("if group.owner_telegram_id == new_owner_id:", 1)[1].split(
        "await session.scalar", 1
    )[0]


def test_explicit_connect_routes_owner_change_through_invalidation() -> None:
    source = _source()
    connect = source.split("async def get_or_create_group", 1)[1].split(
        "async def active_warnings_count", 1
    )[0]
    assert "if create:" in connect
    assert "await _invalidate_marketplace_on_owner_change(session, group, owner_id)" in connect
    assert "group.owner_telegram_id = owner_id" not in connect
