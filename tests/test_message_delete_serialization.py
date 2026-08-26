from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_delete_lock_is_attached_to_primary_group_router() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "group.router.message.middleware(group_mutation_lock_middleware)" in main
    assert "group_owner_mutation_fixes.router" not in main


def test_reply_delete_is_locked_before_authorization_and_side_effect() -> None:
    middleware = (ROOT / "app/middlewares_group_mutation.py").read_text(encoding="utf-8")
    assert '_DELETE_WORDS = {"удалить", "стереть", "удали"}' in middleware
    assert "event.reply_to_message is not None and text in _DELETE_WORDS" in middleware
    assert ".with_for_update()" in middleware

    group = (ROOT / "app/handlers/group.py").read_text(encoding="utf-8")
    delete_handler = group.split("async def delete_message_command", 1)[1].split(
        "@router.message(TextCommandFilter())", 1
    )[0]
    assert delete_handler.index('can_moderate(bot, session, group, message.from_user.id, "delete")') < delete_handler.index(
        "await message.reply_to_message.delete()"
    )
    assert delete_handler.index("await message.reply_to_message.delete()") < delete_handler.index(
        "await session.commit()"
    )


def test_legacy_compatibility_roles_are_not_part_of_delete_lock() -> None:
    middleware = (ROOT / "app/middlewares_group_mutation.py").read_text(encoding="utf-8")
    assert "assign_moderator" not in middleware
    assert "remove_moderator" not in middleware

    access = (ROOT / "app/services/access.py").read_text(encoding="utf-8")
    can_moderate = access.split("async def can_moderate", 1)[1].split(
        "async def can_manage_group", 1
    )[0]
    assert "can_use_rank_permission" in can_moderate
    assert "get_internal_moderator" not in can_moderate
