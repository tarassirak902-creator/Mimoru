from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_execute_locks_group_before_action_and_target_authorization() -> None:
    source = (ROOT / "app/services/moderation.py").read_text(encoding="utf-8")
    start = source.index("async def execute(")
    body = source[start:]

    group_lock = body.index("select(Group).where(Group.id == group_id).with_for_update()")
    action_check = body.index("await can_moderate(bot, session, group, moderator_id, action)")
    target_check = body.index("await can_moderate_target(session, group, moderator_id, target_id)")
    first_telegram = min(
        body.index("await bot.ban_chat_member"),
        body.index("await bot.unban_chat_member"),
        body.index("await bot.restrict_chat_member"),
    )

    assert group_lock < action_check < target_check < first_telegram


def test_execute_denies_lost_action_permission_before_telegram() -> None:
    source = (ROOT / "app/services/moderation.py").read_text(encoding="utf-8")
    start = source.index("if not await can_moderate(bot, session, group, moderator_id, action):")
    end = source.index("allowed, denial = await can_moderate_target", start)
    denial = source[start:end]

    assert 'return _failure("Право на это действие больше недоступно.")' in denial
    assert "bot." not in denial


def test_live_reason_callback_still_uses_shared_execute_boundary() -> None:
    source = (ROOT / "app/handlers/reason_admin.py").read_text(encoding="utf-8")
    start = source.index("async def moderation_reason_selected")
    end = source.index("async def moderation_reason_cancel", start)
    body = source[start:end]

    assert "from app.services.moderation import execute" in source
    assert "result = await execute(" in body
    assert "if result.commit:" in body
    assert "await session.commit()" in body
    assert "await session.rollback()" in body


def test_retired_kick_remains_denied_by_full_permission_check() -> None:
    access = (ROOT / "app/services/access.py").read_text(encoding="utf-8")
    start = access.index("async def can_moderate(")
    end = access.index("async def can_manage_group", start)
    body = access[start:end]

    assert 'if action == "kick":' in body
    assert "return False" in body
