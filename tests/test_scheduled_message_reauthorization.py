from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _tasks_code() -> str:
    return (ROOT / "app/tasks.py").read_text(encoding="utf-8")


def _function_body(code: str, name: str, next_name: str) -> str:
    start = code.index(f"async def {name}")
    end = code.index(f"async def {next_name}", start)
    return code[start:end]


def test_scheduled_delivery_reauthorizes_before_telegram_send() -> None:
    code = _tasks_code()
    body = _function_body(code, "_deliver_scheduled_message", "send_scheduled_messages")

    group_lock = body.index("select(Group).where(Group.id == group_id).with_for_update()")
    row_lock = body.index("select(ScheduledMessage).where(ScheduledMessage.id == row_id).with_for_update()")
    authorization = body.index("row.creator_telegram_id != group.owner_telegram_id")
    send = body.index("await bot.send_message(group.telegram_chat_id, row.text)")
    commit = body.rindex("await session.commit()")

    assert group_lock < row_lock < authorization < send < commit
    assert "not is_service_owner(row.creator_telegram_id)" in body


def test_stale_scheduled_creator_is_terminally_cancelled() -> None:
    code = _tasks_code()
    body = _function_body(code, "_deliver_scheduled_message", "send_scheduled_messages")
    stale_start = body.index("if row.creator_telegram_id != group.owner_telegram_id")
    stale_end = body.index("try:", stale_start)
    stale = body[stale_start:stale_end]

    assert 'row.status = "cancelled"' in stale
    assert 'row.error_text = "Создатель больше не управляет группой"' in stale
    assert "await session.commit()" in stale
    assert "bot.send_message" not in stale


def test_outer_scheduler_only_dispatches_due_ids_to_locked_helper() -> None:
    code = _tasks_code()
    body = _function_body(code, "send_scheduled_messages", "apply_night_modes")

    assert "select(ScheduledMessage.id)" in body
    assert "row_ids" in body
    assert "await _deliver_scheduled_message(bot, row_id, now)" in body
    assert "bot.send_message" not in body


def test_recurring_schedule_keeps_existing_next_occurrence_behavior() -> None:
    code = _tasks_code()
    body = _function_body(code, "_deliver_scheduled_message", "send_scheduled_messages")

    assert "next_at = next_occurrence(row.send_at, row.recurrence)" in body
    assert 'row.status = "sent"' in body
    assert "row.send_at = next_at" in body
    assert 'row.status = "pending"' in body
