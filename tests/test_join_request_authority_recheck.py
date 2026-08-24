from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source() -> str:
    return (ROOT / "app/handlers/join_requests.py").read_text(encoding="utf-8")


def _handler(source: str, name: str) -> str:
    body = source.split(f"async def {name}(", 1)[1]
    next_handler = body.find("\nasync def ")
    next_router = body.find("\n@router.")
    boundaries = [index for index in (next_handler, next_router) if index >= 0]
    return body[: min(boundaries)] if boundaries else body


def test_join_request_management_reuses_locked_owner_boundary() -> None:
    source = _source()
    helper = source.split("async def managed_group(", 1)[1].split("async def abort_invite_operation", 1)[0]
    assert "managed_group_for_message(" in helper
    assert "for_update=for_update" in helper


def test_invite_creation_reauthorizes_after_crash_safe_begin() -> None:
    body = _handler(_source(), "create_invite")
    begin = body.index("await begin_invite_creation(")
    telegram = body.index("await bot.create_chat_invite_link(")
    locks = [
        index
        for index in range(len(body))
        if body.startswith("await managed_group(message, bot, session, for_update=True)", index)
    ]
    assert len(locks) >= 2
    assert locks[0] < begin < locks[1] < telegram
    assert "await abort_invite_operation(session, operation.id)" in body[locks[1]:telegram]


def test_invite_revocation_reauthorizes_after_transition_commit() -> None:
    body = _handler(_source(), "disable_invite")
    telegram = body.index("await bot.revoke_chat_invite_link(")
    second_lock = body.rindex("await managed_group(message, bot, session, for_update=True)", 0, telegram)
    assert "await session.commit()" in body[:second_lock] or "await begin_invite_revocation(" in body[:second_lock]
    assert second_lock < telegram
    assert "await abort_invite_operation(session, operation.id)" in body[second_lock:telegram]


def test_manual_join_review_reauthorizes_after_claim_commit() -> None:
    body = _handler(_source(), "review_request")
    claim = body.index("await claim_join_review(")
    telegram = min(
        body.index("await bot.approve_chat_join_request("),
        body.index("await bot.decline_chat_join_request("),
    )
    locks = [
        index
        for index in range(len(body))
        if body.startswith("await managed_group(message, bot, session, for_update=True)", index)
    ]
    assert len(locks) >= 2
    assert locks[0] < claim < locks[1] < telegram
    assert "await release_failed_join_review(session, row.id, approve=approve)" in body[locks[1]:telegram]


def test_join_request_setting_mutations_lock_but_lists_do_not() -> None:
    source = _source()
    for name in ("toggle_requests", "toggle_auto_approve"):
        assert "for_update=True" in _handler(source, name)
    for name in ("invite_list", "pending_requests"):
        assert "for_update=True" not in _handler(source, name)
