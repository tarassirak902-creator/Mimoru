from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _function(source: str, name: str) -> str:
    body = source.split(f"async def {name}(", 1)[1]
    boundaries = [
        index
        for marker in ("\nasync def ", "\n@router.")
        if (index := body.find(marker)) >= 0
    ]
    return body[: min(boundaries)] if boundaries else body


def test_expiry_claim_is_compare_and_set_from_exact_numeric_deadline() -> None:
    source = (ROOT / "app/services/captcha_state.py").read_text(encoding="utf-8")
    script = source.split('CAPTCHA_EXPIRY_CLAIM_LUA = r"""', 1)[1].split('"""', 1)[0]
    assert "redis.call('GET', KEYS[1])" in script
    assert "current ~= ARGV[1]" in script
    assert "local deadline = tonumber(current)" in script
    assert "deadline > now" in script
    assert "redis.call('SET', KEYS[1], ARGV[3], 'EX', ARGV[4])" in script

    worker = (ROOT / "app/tasks_captcha.py").read_text(encoding="utf-8")
    expiry = _function(worker, "expire_captcha_sessions")
    claim = expiry.index("claim_expired_captcha(redis, key, raw_value, now_ts)")
    won = expiry.index("if claim_result != 1:", claim)
    pending = expiry.index("state = PENDING_BAN", won)
    ban = expiry.index("await _run_pending_ban", pending)
    assert claim < won < pending < ban


def test_verification_claim_only_wins_before_deadline() -> None:
    source = (ROOT / "app/services/captcha_state.py").read_text(encoding="utf-8")
    script = source.split('CAPTCHA_VERIFY_CLAIM_LUA = r"""', 1)[1].split('"""', 1)[0]
    assert "redis.call('GET', KEYS[1])" in script
    assert "local deadline = tonumber(current)" in script
    assert "deadline <= now" in script
    assert "redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[3])" in script
    assert 'VERIFIED = "verified"' in source


def test_callback_claims_verified_before_serialized_unrestrict_finalizer() -> None:
    members = (ROOT / "app/handlers/members.py").read_text(encoding="utf-8")
    body = _function(members, "verification_callback")
    claim = body.index("await claim_verified_captcha(")
    reject = body.index("if claim_result <= 0:", claim)
    finalizer = body.index("await finalize_verified_captcha(", reject)
    commit = body.index("await session.commit()", finalizer)
    assert claim < reject < finalizer < commit
    assert "await bot.restrict_chat_member" not in body
    assert "await redis.delete(" not in body

    service = (ROOT / "app/services/captcha_verification.py").read_text(encoding="utf-8")
    finalizer_body = _function(service, "finalize_verified_captcha")
    telegram = finalizer_body.index("await bot.restrict_chat_member")
    cleanup = finalizer_body.index("await delete_captcha_state(redis, key, VERIFIED)", telegram)
    assert telegram < cleanup


def test_verified_state_is_recovered_through_unrestrict_finalizer_never_ban() -> None:
    tasks = (ROOT / "app/tasks_captcha.py").read_text(encoding="utf-8")
    verified = _function(tasks, "_run_verified")
    assert "await finalize_verified_captcha(" in verified
    assert "await session.commit()" in verified
    assert "ban_chat_member" not in verified

    service = (ROOT / "app/services/captcha_verification.py").read_text(encoding="utf-8")
    finalizer = _function(service, "finalize_verified_captcha")
    assert "await bot.restrict_chat_member" in finalizer
    assert "permissions=UNRESTRICTED" in finalizer
    assert "await delete_captcha_state(redis, key, VERIFIED)" in finalizer
    assert "ban_chat_member" not in finalizer

    expiry = _function(tasks, "expire_captcha_sessions")
    verified_branch = expiry.index("if state == VERIFIED:")
    verified_run = expiry.index("await _run_verified", verified_branch)
    verified_continue = expiry.index("continue", verified_run)
    ban_branch = expiry.index("if state == PENDING_BAN:", verified_continue)
    assert verified_branch < verified_run < verified_continue < ban_branch


def test_cleanup_is_conditional_on_expected_state() -> None:
    source = (ROOT / "app/services/captcha_state.py").read_text(encoding="utf-8")
    script = source.split('CAPTCHA_DELETE_STATE_LUA = r"""', 1)[1].split('"""', 1)[0]
    assert "current ~= ARGV[1]" in script
    assert "redis.call('DEL', KEYS[1])" in script


def test_production_paths_reach_members_callback_and_captcha_worker() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    order = main.split("dp.include_routers(", 1)[1]
    assert "\n        members.router," in order

    members = (ROOT / "app/handlers/members.py").read_text(encoding="utf-8")
    assert '@router.callback_query(F.data.startswith("verify:"))' in members

    delivery = (ROOT / "app/tasks_delivery.py").read_text(encoding="utf-8")
    assert "from app.tasks_captcha import expire_captcha_sessions" in delivery
    loop = delivery.split("async def background_loop(", 1)[1]
    assert "await expire_captcha_sessions(bot, redis)" in loop
