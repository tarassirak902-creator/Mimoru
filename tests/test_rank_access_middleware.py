from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_rank_routers_share_access_mode_middleware():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    text_commands = (ROOT / "app/handlers/rank_text_commands.py").read_text(encoding="utf-8")
    assert "RankAccessModeMiddleware" in main
    assert "for rank_router in (admin_access_mode.router, telegram_roles.router):" in main
    assert "rank_router.callback_query.middleware(rank_access_middleware)" in main
    assert "rank_router.message.middleware(rank_access_middleware)" in main
    assert "router.message.middleware(RankAccessModeMiddleware())" in text_commands


def test_rank_access_middleware_checks_callback_fsm_and_group_chat_context():
    source = (ROOT / "app/middlewares_rank_access.py").read_text(encoding="utf-8")
    assert "event.data.split" in source
    assert 'state_data.get("group_id")' in source
    assert "Group.telegram_chat_id == event.chat.id" in source
    assert "await get_actor_rank_with_access(bot, session, group, user.id)" in source
    assert "show_alert=True" in source
