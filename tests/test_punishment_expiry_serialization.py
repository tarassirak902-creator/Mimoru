from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
# This contract intentionally covers the production scheduler wiring as well as
# the Group-serialized permission release boundary.


def _expiry_body() -> str:
    source = (ROOT / "app/services/punishment_expiry.py").read_text(encoding="utf-8")
    return source.split("async def expire_punishments(bot: Bot, redis: Redis) -> None:", 1)[1]


def test_scheduler_uses_hardened_expiry_service() -> None:
    source = (ROOT / "app/tasks_delivery.py").read_text(encoding="utf-8")
    assert "from app.services.punishment_expiry import expire_punishments" in source
    assert "from app.tasks_warning_expiry import expire_warnings" in source
    assert "from app.tasks import" not in source
    loop = source.split("async def background_loop(", 1)[1]
    assert "await expire_punishments(bot, redis)" in loop


def test_expiry_scans_ids_then_rechecks_under_group_and_punishment_locks() -> None:
    body = _expiry_body()

    scan = body.index("select(Punishment.id).where(")
    loop = body.index("for punishment_id in candidate_ids:", scan)
    group_lock = body.index("select(Group).where(Group.id == group_id).with_for_update()", loop)
    punishment_lock = body.index("select(Punishment)", group_lock)
    punishment_for_update = body.index(".with_for_update()", punishment_lock)
    recheck = body.index("punishment.ends_at > now", punishment_for_update)

    assert scan < loop < group_lock < punishment_lock < punishment_for_update < recheck
    initial_scan = body[scan:loop]
    assert "select(Punishment.id)" in initial_scan
    assert "select(Punishment)" not in initial_scan


def test_expiry_never_releases_while_same_kind_punishment_remains_active() -> None:
    body = _expiry_body()

    deactivate = body.index("punishment.active = False")
    flush = body.index("await session.flush()", deactivate)
    active_check = body.index("another_active = await session.scalar", flush)
    same_group = body.index("Punishment.group_id == punishment.group_id", active_check)
    same_user = body.index("Punishment.user_telegram_id == punishment.user_telegram_id", same_group)
    same_kind = body.index("Punishment.kind == punishment.kind", same_user)
    still_active = body.index("Punishment.active.is_(True)", same_kind)
    guard = body.index("if another_active is not None:", still_active)
    guard_commit = body.index("await session.commit()", guard)
    guard_continue = body.index("continue", guard_commit)
    unmute = body.index("await bot.restrict_chat_member(", guard_continue)
    unban = body.index("await bot.unban_chat_member(", unmute)

    assert deactivate < flush < active_check < same_group < same_user < same_kind < still_active
    assert still_active < guard < guard_commit < guard_continue < unmute < unban


def test_mute_expiry_checks_captcha_owner_before_telegram_unmute() -> None:
    body = _expiry_body()
    group_lock = body.index("select(Group).where(Group.id == group_id).with_for_update()")
    active_check = body.index("another_active = await session.scalar", group_lock)
    active_guard = body.index("if another_active is not None:", active_check)
    mute_branch = body.index('if punishment.kind == "mute":', active_guard)
    captcha_key = body.index('f"captcha:{group.telegram_chat_id}:"', mute_branch)
    captcha_check = body.index("await redis.get(captcha_key)", captcha_key)
    captcha_guard = body.index("is not None:", captcha_check)
    captcha_commit = body.index("await session.commit()", captcha_guard)
    captcha_continue = body.index("continue", captcha_commit)
    telegram_unmute = body.index("await bot.restrict_chat_member(", captcha_continue)

    assert group_lock < active_check < active_guard < mute_branch
    assert mute_branch < captcha_key < captcha_check < captcha_guard
    assert captcha_guard < captcha_commit < captcha_continue < telegram_unmute


def test_group_lock_covers_final_check_telegram_release_and_commit() -> None:
    body = _expiry_body()
    group_lock = body.index("select(Group).where(Group.id == group_id).with_for_update()")
    active_check = body.index("another_active = await session.scalar", group_lock)
    captcha_check = body.index("await redis.get(captcha_key)", active_check)
    telegram_effect = body.index("await bot.restrict_chat_member(", captcha_check)
    final_commit = body.index("await session.commit()", telegram_effect)
    assert group_lock < active_check < captcha_check < telegram_effect < final_commit

    moderation = (ROOT / "app/services/moderation.py").read_text(encoding="utf-8")
    execute = moderation.split("async def execute(", 1)[1]
    assert "select(Group).where(Group.id == group_id).with_for_update()" in execute


def test_telegram_failure_rolls_back_expiry_for_retry() -> None:
    source = (ROOT / "app/services/punishment_expiry.py").read_text(encoding="utf-8")
    body = source.split("except (TelegramBadRequest, TelegramForbiddenError) as error:", 1)[1]
    rollback = body.index("await session.rollback()")
    retry_exit = body.index("continue", rollback)
    assert rollback < retry_exit
