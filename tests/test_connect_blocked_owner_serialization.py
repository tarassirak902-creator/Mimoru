from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_explicit_connect_is_the_only_group_create_winner() -> None:
    handlers = ROOT / "app" / "handlers"
    occurrences: list[tuple[str, int]] = []
    for path in handlers.glob("*.py"):
        count = path.read_text(encoding="utf-8").count("create=True")
        if count:
            occurrences.append((path.name, count))
    assert occurrences == [("group_onboarding_flow.py", 1)]

    handler = _source("app/handlers/group_onboarding_flow.py")
    body = handler.split("async def connect_group_private_first", 1)[1].split(
        "async def open_connected_group_setup", 1
    )[0]
    assert 'F.text.casefold() == "подключить"' in handler
    assert "await is_creator(" in body
    assert "await upsert_user(" in body
    assert "await get_or_create_group(" in body
    assert "GroupOwnerServiceBlockedError" in body


def test_connect_serializes_owner_block_before_group_mutation() -> None:
    repo = _source("app/services/repositories.py")
    body = repo.split("async def get_or_create_group", 1)[1].split(
        "async def active_warnings_count", 1
    )[0]

    owner_lock = "select(User).where(User.telegram_id == owner_id).with_for_update()"
    group_query = "query = select(Group).where(Group.telegram_chat_id == chat.id)"
    group_lock = "query = query.with_for_update()"
    blocked = "if owner.service_blocked:"
    create_group = "group = Group("
    transfer = "await _invalidate_marketplace_on_owner_change(session, group, owner_id)"
    activate = "group.is_active = True"

    assert owner_lock in body
    assert group_query in body and group_lock in body
    assert blocked in body
    assert body.index(owner_lock) < body.index(blocked)
    assert body.index(blocked) < body.index(group_query)
    assert body.index(group_query) < body.index(group_lock)
    assert body.index(blocked) < body.index(create_group)
    assert body.index(group_lock) < body.index(transfer)
    assert body.index(transfer) < body.index(activate)


def test_blocked_connect_aborts_before_admin_sync_or_commit() -> None:
    handler = _source("app/handlers/group_onboarding_flow.py")
    body = handler.split("async def connect_group_private_first", 1)[1].split(
        "async def open_connected_group_setup", 1
    )[0]
    blocked_branch = body.split("except GroupOwnerServiceBlockedError:", 1)[1].split(
        "sync = await sync_telegram_administrators", 1
    )[0]
    assert "await session.rollback()" in blocked_branch
    assert "await message.reply(" in blocked_branch
    assert "sync_telegram_administrators" not in blocked_branch
    assert "await session.commit()" not in blocked_branch

    success = body.split("sync = await sync_telegram_administrators", 1)[1]
    assert "await session.commit()" in success


def test_upsert_does_not_clear_existing_service_block() -> None:
    repo = _source("app/services/repositories.py")
    upsert = repo.split("async def upsert_user", 1)[1].split(
        "async def _invalidate_marketplace_on_owner_change", 1
    )[0]
    update = upsert.split("on_conflict_do_update", 1)[1]
    assert '"username": stmt.excluded.username' in update
    assert '"first_name": stmt.excluded.first_name' in update
    assert '"last_name": stmt.excluded.last_name' in update
    assert '"service_blocked"' not in update


def test_allowed_owner_transfer_keeps_marketplace_invalidation_before_assignment() -> None:
    repo = _source("app/services/repositories.py")
    transfer = repo.split("async def _invalidate_marketplace_on_owner_change", 1)[1].split(
        "async def get_or_create_group", 1
    )[0]
    assert ".with_for_update()" in transfer
    assert "listing.active = False" in transfer
    assert 'deal.status = "cancelled"' in transfer
    assert transfer.index("listing.active = False") < transfer.index(
        "group.owner_telegram_id = new_owner_id"
    )
