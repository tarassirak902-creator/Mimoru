from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_hardened_scheduler_uses_stateful_captcha_expiry():
    source = (ROOT / "app/tasks_delivery.py").read_text(encoding="utf-8")
    assert "from app.tasks_captcha import expire_captcha_sessions" in source
    assert "from app.tasks import" not in source


def test_captcha_expiry_persists_inflight_state_before_ban():
    source = (ROOT / "app/tasks_captcha.py").read_text(encoding="utf-8")
    function = source.split("async def _run_pending_ban", 1)[1].split(
        "async def _run_pending_unban", 1
    )[0]
    state_pos = function.index("await redis.set(key, BAN_INFLIGHT")
    ban_pos = function.index("await bot.ban_chat_member")
    assert state_pos < ban_pos


def test_failed_ban_keeps_retryable_state():
    source = (ROOT / "app/tasks_captcha.py").read_text(encoding="utf-8")
    function = source.split("async def _run_pending_ban", 1)[1].split(
        "async def _run_pending_unban", 1
    )[0]
    assert "captcha_expiry_ban_failed" in function
    assert "await redis.set(key, PENDING_BAN" in function
    assert "await redis.delete(key)" not in function


def test_pending_unban_is_read_back_before_normal_conditional_cleanup():
    source = (ROOT / "app/tasks_captcha.py").read_text(encoding="utf-8")
    function = source.split("async def _run_pending_unban", 1)[1].split(
        "async def expire_captcha_sessions", 1
    )[0]
    read_pos = function.index("await _member_is_banned")
    normal_tail = function[read_pos:]
    cleanup_pos = normal_tail.index("await delete_captcha_state(redis, key, PENDING_UNBAN)")
    assert cleanup_pos > normal_tail.index("await _member_is_banned")
    assert "captcha_expiry_unban_failed" in function
    assert "await redis.delete(key)" not in function


def test_ban_inflight_recovery_uses_telegram_readback():
    source = (ROOT / "app/tasks_captcha.py").read_text(encoding="utf-8")
    expiry = source.split("async def expire_captcha_sessions", 1)[1]
    assert "if state == BAN_INFLIGHT" in expiry
    assert "await _member_is_banned" in expiry
    assert "PENDING_UNBAN if banned else PENDING_BAN" in expiry


def test_state_cleanup_is_conditional_but_malformed_keys_may_be_deleted():
    tasks = (ROOT / "app/tasks_captcha.py").read_text(encoding="utf-8")
    verification = (ROOT / "app/services/captcha_verification.py").read_text(encoding="utf-8")
    pending_unban = tasks.split("async def _run_pending_unban", 1)[1].split(
        "async def expire_captcha_sessions", 1
    )[0]
    verified = tasks.split("async def _run_verified", 1)[1].split(
        "async def _run_pending_ban", 1
    )[0]
    expiry = tasks.split("async def expire_captcha_sessions", 1)[1]
    assert "finally:" not in tasks
    assert "await delete_captcha_state(redis, key, PENDING_UNBAN)" in pending_unban
    assert "await finalize_verified_captcha(" in verified
    assert "await delete_captcha_state(redis, key, VERIFIED)" in verification
    assert "await redis.delete(key)" not in pending_unban
    assert "await redis.delete(key)" not in verified
    assert "await redis.delete(key)" not in verification
    assert "if parsed is None:" in expiry
    assert "await redis.delete(key)" in expiry.split("if parsed is None:", 1)[1].split("chat_id, user_id = parsed", 1)[0]
