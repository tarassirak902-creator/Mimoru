from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_fun_settings_mutation_uses_group_lock_but_read_screen_does_not() -> None:
    source = (ROOT / "app/handlers/fun_extras.py").read_text(encoding="utf-8")
    helper = source.split("async def _group(", 1)[1].split("def _leader", 1)[0]
    assert "for_update: bool = False" in helper
    assert "if for_update:" in helper
    assert "query = query.with_for_update()" in helper

    read_handler = source.split("async def game_settings(", 1)[1].split(
        "async def change_game_settings(", 1
    )[0]
    mutation = source.split("async def change_game_settings(", 1)[1]
    assert "_group(session, message.chat.id, for_update=True)" not in read_handler
    assert "_group(session, message.chat.id, for_update=True)" in mutation


def test_claimed_fun_worker_rechecks_optout_under_group_lock_before_telegram() -> None:
    source = (ROOT / "app/tasks_fun.py").read_text(encoding="utf-8")
    body = source.split("async def _run_claimed_auto_activity(", 1)[1].split(
        "async def run_fun_auto_activity", 1
    )[0]

    group_select = body.index("select(Group)")
    group_lock = body.index(".with_for_update()", group_select)
    settings_select = body.index("select(FunGroupSettings)", group_lock)
    optout = body.index("not settings.auto_enabled", settings_select)
    target_lookup = body.index("await _pick_target", optout)
    send = body.index("await bot.send_message", target_lookup)
    commit = body.index("await session.commit()", send)

    assert group_select < group_lock < settings_select < optout < target_lookup < send < commit


def test_fun_auto_production_reachability() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    extras = (ROOT / "app/handlers/fun_extras.py").read_text(encoding="utf-8")
    tasks = (ROOT / "app/tasks_fun.py").read_text(encoding="utf-8")

    routers = main.split("dp.include_routers(", 1)[1].split(")", 1)[0]
    assert "fun_extras.router" in routers
    assert 'F.text.casefold().regexp(r"^авто игры (вкл|выкл|15-20|30-40|60)$")' in extras
    assert "async def change_game_settings" in extras
    assert "fun_task = asyncio.create_task(fun_background_loop(bot, stop_event)" in main
    assert "async def fun_background_loop" in tasks
    assert "await run_fun_auto_activity(bot)" in tasks
