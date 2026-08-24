from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _pending_unban_body() -> str:
    source = (ROOT / "app/tasks_captcha.py").read_text(encoding="utf-8")
    return source.split("async def _run_pending_unban", 1)[1].split(
        "async def expire_captcha_sessions", 1
    )[0]


def test_pending_unban_locks_group_rechecks_state_and_ban_before_telegram() -> None:
    body = _pending_unban_body()

    session = body.index("SessionFactory()")
    group = body.index("select(Group)", session)
    lock = body.index(".with_for_update()", group)
    state = body.index("await redis.get(key)", lock)
    punishment = body.index("select(Punishment.id)", state)
    kind = body.index('Punishment.kind == "ban"', punishment)
    readback = body.index("await _member_is_banned", kind)
    telegram = body.index("await bot.unban_chat_member", readback)
    cleanup = body.index("await delete_captcha_state(redis, key, PENDING_UNBAN)", telegram)
    commit = body.index("await session.commit()", cleanup)

    assert session < group < lock < state < punishment < kind < readback < telegram < cleanup < commit


def test_active_moderation_ban_finishes_captcha_without_unban() -> None:
    body = _pending_unban_body()
    branch = body.split("if active_ban is not None:", 1)[1].split("banned =", 1)[0]

    cleanup = branch.index("await delete_captcha_state(redis, key, PENDING_UNBAN)")
    commit = branch.index("await session.commit()", cleanup)
    result = branch.index("return", commit)

    assert cleanup < commit < result
    assert "unban_chat_member" not in branch


def test_pending_unban_failures_keep_retryable_state() -> None:
    body = _pending_unban_body()
    failure = body.split(
        "except (TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError) as error:",
        1,
    )[1]

    assert "captcha_expiry_unban_failed" in failure
    before_return = failure.split("return", 1)[0]
    assert "await refresh_captcha_state_ttl(redis, key, PENDING_UNBAN)" in before_return
    assert "delete_captcha_state" not in before_return


def test_pending_unban_worker_is_production_reachable() -> None:
    delivery = (ROOT / "app/tasks_delivery.py").read_text(encoding="utf-8")
    tasks = (ROOT / "app/tasks_captcha.py").read_text(encoding="utf-8")

    assert "from app.tasks_captcha import expire_captcha_sessions" in delivery
    loop = delivery.split("async def background_loop(", 1)[1]
    assert "await expire_captcha_sessions(bot, redis)" in loop

    expiry = tasks.split("async def expire_captcha_sessions", 1)[1]
    pending = expiry.index("if state == PENDING_UNBAN:")
    runner = expiry.index("await _run_pending_unban", pending)
    assert pending < runner
