from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _delivery_source() -> str:
    return (ROOT / "app/tasks_delivery.py").read_text(encoding="utf-8")


def test_daily_report_claim_is_committed_before_telegram_send() -> None:
    source = _delivery_source()
    claim = source.split("async def _claim_daily_report", 1)[1].split(
        "async def send_daily_reports", 1
    )[0]
    sender = source.split("async def send_daily_reports", 1)[1].split(
        "async def _claim_subscription_notice", 1
    )[0]
    owner_delivery = (ROOT / "app/services/owner_notifications.py").read_text(encoding="utf-8")
    assert ".values(last_report_date=local_today)" in claim
    assert "await session.commit()" in claim
    assert sender.index("await _claim_daily_report") < sender.index("await send_to_current_group_owner")
    assert ".with_for_update()" in owner_delivery
    assert "await bot.send_message(owner_id, text)" in owner_delivery


def test_subscription_notice_ledger_is_committed_before_send() -> None:
    source = _delivery_source()
    claim = source.split("async def _claim_subscription_notice", 1)[1].split(
        "async def send_subscription_notices", 1
    )[0]
    sender = source.split("async def send_subscription_notices", 1)[1].split(
        "async def recover_interrupted_scheduled_messages", 1
    )[0]
    owner_delivery = (ROOT / "app/services/owner_notifications.py").read_text(encoding="utf-8")
    assert ".with_for_update()" in claim
    assert "session.add(GroupSubscriptionEvent(" in claim
    assert "await session.commit()" in claim
    assert sender.index("await _claim_subscription_notice") < sender.index("await send_to_current_group_owner")
    assert ".with_for_update()" in owner_delivery
    assert "await bot.send_message(owner_id, text)" in owner_delivery


def test_scheduled_message_pre_send_claim_is_durable() -> None:
    source = _delivery_source()
    claim = source.split("async def _claim_scheduled_message", 1)[1].split(
        "async def _mark_scheduled_message_processing", 1
    )[0]
    sender = source.split("async def send_scheduled_messages", 1)[1].split(
        "async def background_loop", 1
    )[0]
    assert 'ScheduledMessage.status == "pending"' in claim
    assert '.values(status="claimed", last_run_at=now, error_text=None)' in claim
    assert "await session.commit()" in claim
    assert sender.index("await _claim_scheduled_message") < sender.index("await bot.send_message")


def test_scheduled_send_revalidates_current_owner_under_group_lock() -> None:
    source = _delivery_source()
    sender = source.split("async def send_scheduled_messages", 1)[1].split(
        "async def background_loop", 1
    )[0]
    claim = sender.index("await _claim_scheduled_message")
    group_lock = sender.index("select(Group).where(Group.id == row.group_id).with_for_update()")
    owner_check = sender.index("stored.creator_telegram_id != group.owner_telegram_id")
    service_owner = sender.index("not is_service_owner(stored.creator_telegram_id)")
    cancel = sender.index('stored.status = "cancelled"')
    processing = sender.index("await _mark_scheduled_message_processing(stored.id)")
    send = sender.index("await bot.send_message")
    assert claim < group_lock < owner_check < service_owner < cancel < processing < send
    assert "Создатель публикации больше не управляет группой" in sender


def test_stale_claimed_message_retries_but_processing_is_quarantined() -> None:
    source = _delivery_source()
    recovery = source.split("async def recover_interrupted_scheduled_messages", 1)[1].split(
        "async def _claim_scheduled_message", 1
    )[0]
    claimed = recovery.index('ScheduledMessage.status == "claimed"')
    retry = recovery.index('.values(status="pending", last_run_at=None, error_text=None)', claimed)
    processing = recovery.index('ScheduledMessage.status == "processing"', retry)
    quarantine = recovery.index('.values(status="failed", error_text=UNCERTAIN_DELIVERY_ERROR)', processing)
    assert claimed < retry < processing < quarantine
    assert "автоматический повтор отключён" in source


def test_processing_transition_is_durable_after_group_lock_before_send() -> None:
    source = _delivery_source()
    marker = source.split("async def _mark_scheduled_message_processing", 1)[1].split(
        "async def send_scheduled_messages", 1
    )[0]
    sender = source.split("async def send_scheduled_messages", 1)[1].split(
        "async def background_loop", 1
    )[0]

    assert "async with SessionFactory() as marker_session:" in marker
    assert 'ScheduledMessage.status == "claimed"' in marker
    assert '.values(status="processing", last_run_at=datetime.now(timezone.utc))' in marker
    assert marker.index("await marker_session.commit()") < marker.index("return transitioned_id is not None")

    group_lock = sender.index("select(Group).where(Group.id == row.group_id).with_for_update()")
    authorization = sender.index("stored.creator_telegram_id != group.owner_telegram_id", group_lock)
    transition = sender.index("await _mark_scheduled_message_processing(stored.id)", authorization)
    send = sender.index("await bot.send_message", transition)
    final_commit = sender.index("await session.commit()", send)
    assert group_lock < authorization < transition < send < final_commit


def test_leader_runs_hardened_delivery_scheduler() -> None:
    source = (ROOT / "app/services/background_leader.py").read_text(encoding="utf-8")
    assert "from app.tasks_delivery import background_loop" in source
    assert "from app.tasks import background_loop" not in source
