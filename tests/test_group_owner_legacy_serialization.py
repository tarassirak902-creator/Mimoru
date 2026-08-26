from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_group_mutation_lock_is_attached_to_primary_group_router() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "group.router.message.middleware(group_mutation_lock_middleware)" in main
    assert "group_owner_mutation_fixes.router" not in main


def test_scoped_owner_mutations_take_group_lock_in_middleware() -> None:
    source = (ROOT / "app/middlewares_group_mutation.py").read_text(encoding="utf-8")
    assert "class GroupMutationLockMiddleware" in source
    assert ".with_for_update()" in source
    assert "Group.telegram_chat_id == event.chat.id" in source

    for command_fragment in (
        "антифлуд",
        "ссылки",
        "капча",
        "приветствие",
        "добавить слово",
        "удалить слово",
        "добавить подписку",
        "удалить подписку",
    ):
        assert command_fragment in source


def test_scope_covers_only_mutations_not_read_lists_or_legacy_roles() -> None:
    source = (ROOT / "app/middlewares_group_mutation.py").read_text(encoding="utf-8")
    assert "list_words" not in source
    assert "list_required_channels" not in source
    assert "assign_moderator" not in source
    assert "remove_moderator" not in source


def test_plan_limited_mutations_run_after_locked_boundary() -> None:
    middleware = (ROOT / "app/middlewares_group_mutation.py").read_text(encoding="utf-8")
    legacy = (ROOT / "app/handlers/group.py").read_text(encoding="utf-8")
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")

    assert ".with_for_update()" in middleware
    assert "group.router.message.middleware(group_mutation_lock_middleware)" in main
    assert "plan_limit(group, \"words\")" in legacy
    assert "plan_limit(group, \"channels\")" in legacy
