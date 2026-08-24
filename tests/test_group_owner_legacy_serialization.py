from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_serialized_router_wins_before_legacy_group_router() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    include = main.split("dp.include_routers(", 1)[1].split(")", 1)[0]
    assert include.index("group_owner_mutation_fixes.router") < include.index("group.router")


def test_scoped_legacy_owner_mutations_take_group_lock_before_delegate() -> None:
    source = (ROOT / "app/handlers/group_owner_mutation_fixes.py").read_text(encoding="utf-8")
    helper = source.split("async def _locked_owner_delegate", 1)[1].split(
        "@router.message", 1
    )[0]
    handler = source.split("async def serialized_legacy_owner_mutation", 1)[1]

    assert "managed_group_for_message(" in helper
    assert "for_update=True" in helper
    assert helper.index("for_update=True") < helper.index("await handler(message, bot, session)")

    for delegated in (
        "legacy_group.toggle_antiflood",
        "legacy_group.toggle_links",
        "legacy_group.toggle_captcha",
        "legacy_group.toggle_welcome",
        "legacy_group.add_word",
        "legacy_group.remove_word",
        "legacy_group.add_required_channel",
        "legacy_group.remove_required_channel",
    ):
        assert delegated in handler


def test_scope_covers_only_mutations_not_read_lists_or_legacy_roles() -> None:
    source = (ROOT / "app/handlers/group_owner_mutation_fixes.py").read_text(encoding="utf-8")

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

    assert "list_words" not in source
    assert "list_required_channels" not in source
    assert "assign_moderator" not in source
    assert "remove_moderator" not in source


def test_plan_limited_mutations_run_only_after_locked_boundary() -> None:
    fixes = (ROOT / "app/handlers/group_owner_mutation_fixes.py").read_text(encoding="utf-8")
    legacy = (ROOT / "app/handlers/group.py").read_text(encoding="utf-8")

    assert "for_update=True" in fixes
    assert "plan_limit(group, \"words\")" in legacy
    assert "plan_limit(group, \"channels\")" in legacy
