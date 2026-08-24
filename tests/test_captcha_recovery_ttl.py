from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_captcha_state_refresh_is_compare_and_expire() -> None:
    source = (ROOT / "app/services/captcha_state.py").read_text(encoding="utf-8")
    assert "CAPTCHA_REFRESH_STATE_LUA" in source
    assert "if current ~= ARGV[1] then" in source
    assert "redis.call('EXPIRE', KEYS[1], ARGV[2])" in source
    assert "async def refresh_captcha_state_ttl" in source
    assert "PROCESSING_TTL_SECONDS" in source


def test_expiry_recovery_refreshes_retained_ambiguous_states() -> None:
    source = (ROOT / "app/tasks_captcha.py").read_text(encoding="utf-8")
    assert "TelegramNetworkError" in source
    assert "refresh_captcha_state_ttl(redis, key, BAN_INFLIGHT)" in source
    assert source.count("refresh_captcha_state_ttl(redis, key, PENDING_UNBAN)") >= 2

    inflight_readback = source.index("if banned is None:", source.index("if state == BAN_INFLIGHT:"))
    inflight_refresh = source.index(
        "refresh_captcha_state_ttl(redis, key, BAN_INFLIGHT)",
        inflight_readback,
    )
    assert inflight_readback < inflight_refresh

    pending_unban = source.index("async def _run_pending_unban")
    readback_retry = source.index("if banned is None:", pending_unban)
    readback_refresh = source.index(
        "refresh_captcha_state_ttl(redis, key, PENDING_UNBAN)",
        readback_retry,
    )
    assert readback_retry < readback_refresh

    unban_call = source.index("await bot.unban_chat_member", pending_unban)
    unban_failure_refresh = source.index(
        "refresh_captcha_state_ttl(redis, key, PENDING_UNBAN)",
        unban_call,
    )
    assert unban_call < unban_failure_refresh


def test_verified_unrestrict_retry_refreshes_recovery_state() -> None:
    source = (ROOT / "app/services/captcha_verification.py").read_text(encoding="utf-8")
    assert "TelegramNetworkError" in source
    telegram_call = source.index("await bot.restrict_chat_member")
    refresh = source.index("refresh_captcha_state_ttl(redis, key, VERIFIED)", telegram_call)
    retry = source.index("return VERIFICATION_RETRY", refresh)
    assert telegram_call < refresh < retry
