from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "app/tasks_delivery.py").read_text(encoding="utf-8")


def _function(name: str) -> str:
    marker = f"async def {name}("
    start = SOURCE.index(marker)
    next_start = SOURCE.find("\n\nasync def ", start + len(marker))
    return SOURCE[start:] if next_start == -1 else SOURCE[start:next_start]


def test_subscription_notice_claim_revalidates_expiry_under_group_lock() -> None:
    claim = _function("_claim_subscription_notice")
    group_lock = claim.index("select(Group)")
    for_update = claim.index(".with_for_update()", group_lock)
    expiry_check = claim.index("locked_group.plan_expires_at != expected_expires_at")
    ledger_add = claim.index("session.add(GroupSubscriptionEvent")
    commit = claim.index("await session.commit()")

    assert group_lock < for_update < expiry_check < ledger_add < commit
    assert 'locked_group.plan_code not in {"trial", "standard", "pro"}' in claim
    assert "locked_group.owner_telegram_id is None" in claim


def test_subscription_notice_message_uses_locked_claim_snapshot() -> None:
    send = _function("send_subscription_notices")
    claim_call = send.index("claim = await _claim_subscription_notice")
    unpack = send.index("title, plan_code, claimed_expires_at = claim", claim_call)
    text = send.index("notice_text =", unpack)
    external_send = send.index("await send_to_current_group_owner", text)

    assert claim_call < unpack < text < external_send
    notice = send[text:external_send]
    assert "{title}" in notice
    assert "{plan_code.upper()}" in notice
    assert "{claimed_expires_at:%d.%m.%Y %H:%M}" in notice
    assert "{group.plan_code" not in notice
    assert "{expires_at:" not in notice


def test_subscription_notice_claim_stays_durable_before_telegram_send() -> None:
    claim = _function("_claim_subscription_notice")
    send = _function("send_subscription_notices")
    assert "await session.commit()" in claim
    assert send.index("await _claim_subscription_notice") < send.index("await send_to_current_group_owner")


def test_production_background_loop_uses_hardened_subscription_notices() -> None:
    background = _function("background_loop")
    assert "await send_subscription_notices(bot)" in background

    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "leader_background_loop" in main
    assert 'name="background-loop"' in main
