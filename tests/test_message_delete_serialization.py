from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_serialized_delete_wins_before_legacy_group_router() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    include = main.split("dp.include_routers(", 1)[1].split(")", 1)[0]
    assert include.index("group_owner_mutation_fixes.router") < include.index("group.router")


def test_reply_delete_is_locked_before_legacy_authorization_and_side_effect() -> None:
    fixes = (ROOT / "app/handlers/group_owner_mutation_fixes.py").read_text(encoding="utf-8")
    handler = fixes.split("async def serialized_legacy_message_delete", 1)[1]

    assert 'F.text.casefold().in_({"удалить", "стереть", "удали"})' in fixes
    assert "F.reply_to_message" in fixes
    assert ".with_for_update()" in handler
    assert handler.index(".with_for_update()") < handler.index(
        "await legacy_group.delete_message_command(message, bot, session)"
    )

    legacy = (ROOT / "app/handlers/group.py").read_text(encoding="utf-8")
    delete_handler = legacy.split("async def delete_message_command", 1)[1].split(
        "@router.message(TextCommandFilter())", 1
    )[0]
    assert delete_handler.index('can_moderate(bot, session, group, message.from_user.id, "delete")') < delete_handler.index(
        "await message.reply_to_message.delete()"
    )
    assert delete_handler.index("await message.reply_to_message.delete()") < delete_handler.index(
        "await session.commit()"
    )


def test_legacy_compatibility_roles_are_not_part_of_delete_fix() -> None:
    fixes = (ROOT / "app/handlers/group_owner_mutation_fixes.py").read_text(encoding="utf-8")
    delete_handler = fixes.split("async def serialized_legacy_message_delete", 1)[1]
    assert "assign_moderator" not in delete_handler
    assert "remove_moderator" not in delete_handler

    access = (ROOT / "app/services/access.py").read_text(encoding="utf-8")
    can_moderate = access.split("async def can_moderate", 1)[1].split(
        "async def can_manage_group", 1
    )[0]
    assert "can_use_rank_permission" in can_moderate
    assert "get_internal_moderator" not in can_moderate
