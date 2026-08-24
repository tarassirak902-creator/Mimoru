from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _atomic_source() -> str:
    return (ROOT / "app/handlers/ad_market_atomic.py").read_text(encoding="utf-8")


def test_atomic_router_wins_required_listing_mutations() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    include = main.split("dp.include_routers(", 1)[1].split(")", 1)[0]
    assert include.index("ad_market_atomic.router") < include.index("ad_market_v3.router")

    source = _atomic_source()
    assert '@router.callback_query(F.data.regexp(r"^reqlist:toggle:\\d+$"))' in source
    assert '@router.message(RequiredListingForm.price, F.chat.type == "private")' in source


def test_final_listing_save_locks_group_before_listing() -> None:
    source = _atomic_source()
    function = source.split("async def atomic_required_listing_price", 1)[1].split(
        "async def atomic_required_listing_toggle", 1
    )[0]
    group_lock = function.index("select(Group)")
    owner_check = function.index("Group.owner_telegram_id == message.from_user.id")
    group_for_update = function.index(".with_for_update()", group_lock)
    listing_lock = function.index("select(RequiredAdListing)")
    listing_for_update = function.index(".with_for_update()", listing_lock)
    activate = function.index("listing.active = True")
    commit = function.index("await session.commit()")
    assert group_lock < owner_check < group_for_update < listing_lock < listing_for_update < activate < commit


def test_toggle_locks_group_before_listing_and_reauthorizes_seller() -> None:
    source = _atomic_source()
    function = source.split("async def atomic_required_listing_toggle", 1)[1].split(
        "async def atomic_required_deal_target", 1
    )[0]
    group_id_lookup = function.index("select(RequiredAdListing.seller_group_id)")
    group_lock = function.index("select(Group)")
    owner_check = function.index("Group.owner_telegram_id == callback.from_user.id")
    group_for_update = function.index(".with_for_update()", group_lock)
    listing_lock = function.index("select(RequiredAdListing)", group_lock)
    listing_for_update = function.index(".with_for_update()", listing_lock)
    seller_check = function.index("listing.seller_owner_telegram_id != callback.from_user.id")
    mutation = function.index("listing.active = not listing.active")
    commit = function.index("await session.commit()")
    assert (
        group_id_lookup
        < group_lock
        < owner_check
        < group_for_update
        < listing_lock
        < listing_for_update
        < seller_check
        < mutation
        < commit
    )


def test_read_and_fsm_start_paths_remain_non_locking() -> None:
    legacy = (ROOT / "app/handlers/ad_market_v3.py").read_text(encoding="utf-8")
    group_view = legacy.split("async def required_listing_group", 1)[1].split(
        "async def required_listing_start", 1
    )[0]
    start = legacy.split("async def required_listing_start", 1)[1].split(
        "async def required_min_days_input", 1
    )[0]
    unit = legacy.split("async def required_unit", 1)[1].split(
        "async def required_price_input", 1
    )[0]
    assert "with_for_update" not in group_view
    assert "with_for_update" not in start
    assert "with_for_update" not in unit
