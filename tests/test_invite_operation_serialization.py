from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _body(code: str, start_name: str, end_name: str) -> str:
    start = code.index(f"async def {start_name}")
    end = code.index(f"async def {end_name}", start)
    return code[start:end]


def test_invite_creation_locks_and_reauthorizes_before_telegram() -> None:
    code = (ROOT / "app/services/invite_execution.py").read_text(encoding="utf-8")
    helper = _body(code, "execute_invite_creation", "execute_invite_revocation")

    group_lock = helper.index("_locked_group_and_operation(session, operation_id)")
    auth = helper.index("_actor_still_authorized(group, operation.actor_telegram_id)")
    telegram = helper.index("await bot.create_chat_invite_link(")
    commit = helper.rindex("await session.commit()")

    assert group_lock < auth < telegram < commit
    assert 'operation.status = "cancelled"' in helper[:telegram]
    assert "async with session.begin_nested():" in helper
    assert "await bot.revoke_chat_invite_link(group.telegram_chat_id, link.invite_link)" in helper


def test_invite_revocation_locks_and_reauthorizes_before_telegram() -> None:
    code = (ROOT / "app/services/invite_execution.py").read_text(encoding="utf-8")
    start = code.index("async def execute_invite_revocation")
    helper = code[start:]

    group_operation_lock = helper.index("_locked_group_and_operation(session, operation_id)")
    campaign_lock = helper.index("select(InviteCampaign)")
    auth = helper.index("_actor_still_authorized(group, operation.actor_telegram_id)")
    telegram = helper.index("await bot.revoke_chat_invite_link(group.telegram_chat_id, invite_link)")
    commit = helper.rindex("await session.commit()")

    assert group_operation_lock < campaign_lock < auth < telegram < commit
    assert 'operation.status = "cancelled"' in helper[:telegram]
    assert "operation.status = REVOKE_UNCERTAIN" in helper


def test_group_is_locked_before_invite_operation_row() -> None:
    code = (ROOT / "app/services/invite_execution.py").read_text(encoding="utf-8")
    helper = _body(code, "_locked_group_and_operation", "execute_invite_creation")
    group_lock = helper.index("select(Group).where(Group.id == group_id).with_for_update()")
    operation_lock = helper.index(
        "select(InviteOperation).where(InviteOperation.id == operation_id).with_for_update()"
    )
    assert group_lock < operation_lock


def test_hardened_invite_router_wins_before_legacy_router() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert main.index("invite_operation_guard.router") < main.index("join_requests.router")

    hardened = (ROOT / "app/handlers/invite_operation_guard.py").read_text(encoding="utf-8")
    legacy = (ROOT / "app/handlers/join_requests.py").read_text(encoding="utf-8")
    for pattern in (
        'F.text.regexp(r"(?i)^создать ссылку(?:-заявку| заявку)? .+")',
        'F.text.regexp(r"(?i)^отключить ссылку \\d+$")',
    ):
        assert pattern in hardened
        assert pattern in legacy
    assert "execute_invite_creation" in hardened
    assert "execute_invite_revocation" in hardened
