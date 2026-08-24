from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_immunity_toggle_locks_group_before_reading_or_mutating_immunity() -> None:
    source = (ROOT / "app/handlers/fun_preferences.py").read_text(encoding="utf-8")
    body = source.split("async def toggle_fun_immunity", 1)[1]

    group_select = body.index("select(Group)")
    group_lock = body.index(".with_for_update()", group_select)
    immunity_select = body.index("select(FunAutoImmunity)", group_lock)
    commit = body.index("await session.commit()", immunity_select)
    reply = body.index("await message.reply", commit)

    assert group_select < group_lock < immunity_select < commit < reply


def test_final_auto_worker_reads_immunity_after_same_group_lock_and_before_send() -> None:
    """Immunity and member scan happen in Phase 1 under Group FOR UPDATE.
    Telegram calls (_pick_target, send_message) happen without connection held."""
    source = (ROOT / "app/tasks_fun.py").read_text(encoding="utf-8")
    body = source.split("async def _run_claimed_auto_activity(", 1)[1].split(
        "async def run_fun_auto_activity", 1
    )[0]

    group_select = body.index("select(Group)")
    group_lock = body.index(".with_for_update()", group_select)
    immunity = body.index("select(FunAutoImmunity.user_telegram_id)", group_lock)
    filter_members = body.index("row[1] not in immune_ids", immunity)
    target_lookup = body.index("await _pick_target", filter_members)
    send = body.index("await bot.send_message", target_lookup)
    commit = body.index("await session.commit()", send)

    assert group_select < group_lock < immunity < filter_members < target_lookup < send < commit


def test_immunity_and_auto_worker_are_production_reachable() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    preferences = (ROOT / "app/handlers/fun_preferences.py").read_text(encoding="utf-8")
    tasks = (ROOT / "app/tasks_fun.py").read_text(encoding="utf-8")

    routers = main.split("dp.include_routers(", 1)[1].split(")", 1)[0]
    assert routers.index("fun_preferences.router") < routers.index("fun_extras.router")
    assert '@router.message(Command("imunitet")' in preferences
    assert "async def toggle_fun_immunity" in preferences
    assert "fun_task = asyncio.create_task(fun_background_loop(bot, stop_event)" in main
    assert "async def _run_claimed_auto_activity" in tasks
