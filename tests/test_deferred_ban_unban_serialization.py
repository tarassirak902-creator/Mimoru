from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_deferred_join_enforcement_locks_before_ban_authority_and_telegram() -> None:
    source = (ROOT / "app/handlers/deferred_bans.py").read_text(encoding="utf-8")
    body = source.split("async def enforce_pending_ban_on_join", 1)[1]

    group_lock = body.index("_group(session, message.chat.id, for_update=True)")
    pending = body.index("await _pending_for", group_lock)
    active_ban = body.index("select(Punishment)", pending)
    telegram_ban = body.index("await bot.ban_chat_member", active_ban)
    ensure = body.index("await _ensure_punishment", telegram_ban)
    commit = body.index("await session.commit()", ensure)

    assert group_lock < pending < active_ban < telegram_ban < ensure < commit


def test_explicit_unban_uses_same_group_serialization_boundary() -> None:
    source = (ROOT / "app/handlers/deferred_bans.py").read_text(encoding="utf-8")
    body = source.split("async def unban_reference", 1)[1].split(
        "async def enforce_pending_ban_on_join", 1
    )[0]

    group_lock = body.index("_group(session, message.chat.id, for_update=True)")
    pending = body.index("select(PendingBan)", group_lock)
    punishments = body.index("select(Punishment)", pending)
    telegram_unban = body.index("await bot.unban_chat_member", punishments)
    commit = body.index("await session.commit()", telegram_unban)

    assert group_lock < pending < punishments < telegram_unban < commit


def test_deferred_ban_join_logic_is_helper_of_single_members_winner() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    deferred = (ROOT / "app/handlers/deferred_bans.py").read_text(encoding="utf-8")
    members = (ROOT / "app/handlers/members.py").read_text(encoding="utf-8")

    routers = main.split("dp.include_routers(", 1)[1].split(")", 1)[0]
    assert "deferred_bans.router" in routers
    assert "members.router" in routers
    assert "@router.message(F.chat.type.in_(GROUP_TYPES), F.new_chat_members)" not in deferred
    assert "async def enforce_pending_ban_on_join" in deferred
    assert "@router.message(F.new_chat_members)" in members
    welcome = members.split("async def welcome", 1)[1].split("async def verification_callback", 1)[0]
    assert "banned_user_ids = await enforce_pending_ban_on_join(message, bot, session)" in welcome
