from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_verified_finalizer_locks_group_and_checks_active_mute_before_unrestrict() -> None:
    source = (ROOT / "app/services/captcha_verification.py").read_text(encoding="utf-8")
    body = source.split("async def finalize_verified_captcha", 1)[1]

    group = body.index("select(Group)")
    lock = body.index(".with_for_update()", group)
    state = body.index("await redis.get(key)", lock)
    mute = body.index("select(Punishment.id)", state)
    kind = body.index('Punishment.kind == "mute"', mute)
    telegram = body.index("await bot.restrict_chat_member", kind)
    cleanup = body.index("await delete_captcha_state(redis, key, VERIFIED)", telegram)

    assert group < lock < state < mute < kind < telegram < cleanup


def test_active_mute_finishes_captcha_without_telegram_unrestrict() -> None:
    source = (ROOT / "app/services/captcha_verification.py").read_text(encoding="utf-8")
    body = source.split("if active_mute is not None:", 1)[1].split("try:", 1)[0]

    cleanup = body.index("await delete_captcha_state(redis, key, VERIFIED)")
    result = body.index("return VERIFICATION_MUTED", cleanup)
    assert cleanup < result
    assert "restrict_chat_member" not in body


def test_callback_claims_verified_then_uses_serialized_finalizer_and_commits() -> None:
    source = (ROOT / "app/handlers/members.py").read_text(encoding="utf-8")
    body = source.split("async def verification_callback", 1)[1].split(
        "async def track_chat_member_update", 1
    )[0]

    claim = body.index("await claim_verified_captcha")
    finalizer = body.index("await finalize_verified_captcha", claim)
    commit = body.index("await session.commit()", finalizer)
    assert claim < finalizer < commit
    assert "permissions=UNRESTRICTED" not in body


def test_verified_background_recovery_uses_same_finalizer() -> None:
    source = (ROOT / "app/tasks_captcha.py").read_text(encoding="utf-8")
    body = source.split("async def _run_verified", 1)[1].split(
        "async def _run_pending_ban", 1
    )[0]

    session = body.index("SessionFactory()")
    finalizer = body.index("await finalize_verified_captcha", session)
    commit = body.index("await session.commit()", finalizer)
    assert session < finalizer < commit
    assert "restrict_chat_member" not in body


def test_captcha_success_and_recovery_are_production_reachable() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    members = (ROOT / "app/handlers/members.py").read_text(encoding="utf-8")
    delivery = (ROOT / "app/tasks_delivery.py").read_text(encoding="utf-8")

    routers = main.split("dp.include_routers(", 1)[1].split(")", 1)[0]
    assert "members.router" in routers
    assert 'callback_data=f"verify:{chat_id}:{user_id}"' in members
    assert '@router.callback_query(F.data.startswith("verify:"))' in members
    assert "from app.tasks_captcha import expire_captcha_sessions" in delivery
    assert "await expire_captcha_sessions(bot, redis)" in delivery
