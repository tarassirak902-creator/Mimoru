from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_rank_mutation_middleware_locks_only_reachable_mutations() -> None:
    source = (ROOT / "app/handlers/rank_legacy_guard.py").read_text(encoding="utf-8")
    assert '_RANK_MUTATION_PREFIXES = ("rank_perm:", "rank_reset:")' in source
    prefixes = source.split("_RANK_MUTATION_PREFIXES", 1)[1].split("_MEDIA_MUTATION_WORDS", 1)[0]
    assert '"rank_change:"' not in prefixes
    assert '"rank_remove:"' not in prefixes
    assert '_MEDIA_MUTATION_WORDS = {"без медиа", "медиа выкл", "медиа вкл"}' in source

    middleware = source.split("class RankMutationLockMiddleware", 1)[1].split("group_action_aliases.router", 1)[0]
    assert ".with_for_update()" in middleware
    assert middleware.index(".with_for_update()") < middleware.rindex("return await handler(event, data)")
    assert "Group.telegram_chat_id == chat_id" in middleware


def test_rank_mutation_middleware_is_scoped_to_telegram_roles() -> None:
    source = (ROOT / "app/handlers/rank_legacy_guard.py").read_text(encoding="utf-8")
    assert "telegram_roles.router.callback_query.middleware(RankMutationLockMiddleware())" in source
    assert "telegram_roles.router.message.middleware(RankMutationLockMiddleware())" in source


def test_active_rank_handlers_reauthorize_after_router_lock() -> None:
    source = (ROOT / "app/handlers/telegram_roles.py").read_text(encoding="utf-8")

    permission = source.split("async def rank_permission_toggle(", 1)[1].split("@router.", 1)[0]
    reset = source.split("async def rank_permission_reset(", 1)[1].split("@router.", 1)[0]
    media = source.split("async def media_restriction(", 1)[1].split("@router.", 1)[0]

    assert "await can_edit_assignment(" in permission
    assert "await session.commit()" in permission
    assert "await can_edit_assignment(" in reset
    assert "await session.commit()" in reset
    assert media.index("await actor_has_permission(") < media.index("await can_moderate_target(") < media.index("await bot.restrict_chat_member(")


def test_rank_remove_is_owned_by_earlier_provisioning_router() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    order = main.split("dp.include_routers(", 1)[1]
    assert order.index("rank_provisioning_handlers.router") < order.index("telegram_roles.router")

    provisioning = (ROOT / "app/handlers/rank_provisioning_handlers.py").read_text(encoding="utf-8")
    assert 'F.data.regexp(r"^rank_remove:\\d+:\\d+$")' in provisioning
    service = (ROOT / "app/services/rank_provisioning.py").read_text(encoding="utf-8")
    execute = service.split("async def _execute_live_intent(", 1)[1].split("async def provision_assignment(", 1)[0]
    assert execute.index(".with_for_update()") < execute.index("await can_remove_assignment(") < execute.index("await demote_telegram_admin(")
