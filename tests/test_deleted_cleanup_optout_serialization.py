from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_deleted_cleanup_rechecks_owner_settings_under_group_lock() -> None:
    """Phase 1 validates automation_enabled, schedule and retry under Group FOR UPDATE."""
    source = (ROOT / "app/tasks_deleted_cleanup.py").read_text(encoding="utf-8")
    body = source.split("async def run_group_automation", 1)[1]

    candidates = body.index("select(Group.id)")
    group_lock = body.index("select(Group)", candidates + 1)
    for_update = body.index(".with_for_update()", group_lock)
    enabled = body.index("not settings.automation_enabled")
    schedule = body.index('schedule not in {"weekly", "monthly"}')
    retry = body.index("await session.get(DeletedCleanupRetry", schedule)
    telegram_chat_id = body.index("telegram_chat_id = group.telegram_chat_id", retry)

    assert candidates < group_lock < for_update < enabled < schedule < retry < telegram_chat_id


def test_deleted_cleanup_group_lock_covers_destructive_telegram_effects() -> None:
    """Telegram ban calls happen between Phase 1 (for_update) and Phase 3 (commit),
    with the connection released during Telegram round-trips."""
    worker = (ROOT / "app/tasks_deleted_cleanup.py").read_text(encoding="utf-8")
    service = (ROOT / "app/services/deleted_accounts.py").read_text(encoding="utf-8")
    body = worker.split("async def run_group_automation", 1)[1]

    assert ".with_for_update()" in body
    assert "_scan_known_members_per_item" in body
    assert "_remove_deleted_accounts_per_item" in body
    assert "await session.commit()" in body
    cleanup = service.split("async def remove_deleted_accounts", 1)[1]
    assert "await _telegram_call(" in cleanup
    assert "bot.ban_chat_member(" in cleanup


def test_owner_automation_optout_uses_same_group_lock_boundary() -> None:
    source = (ROOT / "app/handlers/automation.py").read_text(encoding="utf-8")
    helper = source.split("async def owned_group", 1)[1].split("async def automation_home", 1)[0]
    toggle = source.split("async def automation_toggle", 1)[1].split("async def cleanup_screen", 1)[0]
    cleanup_set = source.split("async def cleanup_set", 1)[1].split("async def warnings_screen", 1)[0]

    assert "query = query.with_for_update()" in helper
    assert "for_update=True" in toggle
    assert "for_update=True" in cleanup_set
    assert "automation_enabled" in toggle
    assert "deleted_cleanup_schedule" in cleanup_set


def test_production_scheduler_reaches_serialized_deleted_cleanup_worker() -> None:
    delivery = (ROOT / "app/tasks_delivery.py").read_text(encoding="utf-8")
    leader = (ROOT / "app/services/background_leader.py").read_text(encoding="utf-8")
    assert "from app.tasks_deleted_cleanup import run_group_automation" in delivery
    assert "await run_group_automation(bot)" in delivery
    assert "from app.tasks_delivery import background_loop" in leader
