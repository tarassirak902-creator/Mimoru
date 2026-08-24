from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source() -> str:
    return (ROOT / "app/services/group_disconnects.py").read_text(encoding="utf-8")


def test_disconnect_revalidates_actor_under_group_lock_before_leave() -> None:
    source = _source()
    body = source.split("async def attempt_group_disconnect", 1)[1].split(
        "async def recover_group_disconnects", 1
    )[0]
    finalize = source.split("async def _finalize_disconnect", 1)[1].split(
        "async def attempt_group_disconnect", 1
    )[0]

    group_lock = body.index("select(Group).where(Group.id == group_id).with_for_update()")
    intent_lock = body.index("select(GroupDisconnectIntent)")
    stale_check = body.index("intent.actor_telegram_id != group.owner_telegram_id")
    service_owner = body.index("is_service_owner(intent.actor_telegram_id)")
    stale_drop = body.index('"group_disconnect_stale_actor_dropped"')
    leave = body.index("await bot.leave_chat(chat_id)")
    finalize_call = body.rindex("await _finalize_disconnect(session, group, intent)")

    assert group_lock < intent_lock < stale_check < service_owner < stale_drop < leave
    assert leave < finalize_call
    assert "group.is_active = False" in finalize
    assert finalize.index("group.is_active = False") < finalize.index("await session.commit()")


def test_stale_owner_disconnect_is_dropped_without_external_side_effect() -> None:
    source = _source()
    body = source.split("async def attempt_group_disconnect", 1)[1].split(
        "async def recover_group_disconnects", 1
    )[0]
    stale_branch = body.split(
        "elif (\n            intent.actor_telegram_id != group.owner_telegram_id", 1
    )[1].split('intent.status = "leaving"', 1)[0]

    assert "await session.delete(intent)" in stale_branch
    assert "await session.commit()" in stale_branch
    assert "leave_chat" not in stale_branch


def test_retryable_disconnect_keeps_authorized_intent_pending() -> None:
    source = _source()
    body = source.split("async def attempt_group_disconnect", 1)[1].split(
        "async def recover_group_disconnects", 1
    )[0]
    error_branch = body.split("except (TelegramBadRequest, TelegramForbiddenError) as error:", 1)[1]

    assert 'intent.status = "pending"' in error_branch
    assert "intent.error_text = str(error)[:1000]" in error_branch
    assert "await session.commit()" in error_branch
    assert "return await _finalize_disconnect(session, group, intent)" in error_branch


def test_recovery_uses_hardened_attempt_path() -> None:
    source = _source()
    recovery = source.split("async def recover_group_disconnects", 1)[1]
    assert "await attempt_group_disconnect(bot, group_id)" in recovery
