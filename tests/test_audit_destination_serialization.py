from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDLERS = ROOT / "app" / "handlers"


def _function(source: str, name: str, next_name: str | None = None) -> str:
    start = source.index(f"async def {name}")
    if next_name is None:
        return source[start:]
    return source[start:source.index(f"async def {next_name}", start)]


def test_audit_text_winners_are_reachable_and_unique() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    audit = (HANDLERS / "audit.py").read_text(encoding="utf-8")
    commands = (ROOT / "app/utils/commands.py").read_text(encoding="utf-8")

    assert "audit.router" in main
    assert 'F.text.casefold() == "журнал сюда"' in audit
    assert 'F.text.casefold() == "журнал выкл"' in audit
    assert 'F.text.casefold() == "журнал тест"' in audit
    assert 'F.text.casefold() == "журнал статус"' in audit
    assert '"журнал"' not in commands

    for command in ("журнал сюда", "журнал выкл", "журнал тест", "журнал статус"):
        owners = [
            path.name
            for path in HANDLERS.glob("*.py")
            if f'"{command}"' in path.read_text(encoding="utf-8")
        ]
        assert owners == ["audit.py"]


def test_audit_mutations_lock_group_before_current_owner_authorization() -> None:
    source = (HANDLERS / "audit.py").read_text(encoding="utf-8")
    owner = _function(source, "owner_group", "audit_here")

    for_update = owner.index("if for_update:")
    lock = owner.index(".with_for_update()", for_update)
    authorize = owner.index("can_manage_group", lock)
    assert for_update < lock < authorize

    assert "owner_group(message, bot, session, for_update=True)" in _function(
        source, "audit_here", "audit_off"
    )
    assert "owner_group(message, bot, session, for_update=True)" in _function(
        source, "audit_off", "audit_status"
    )
    assert "owner_group(message, bot, session, for_update=True)" in _function(
        source, "audit_test"
    )

    # Status is deliberately read-only and must not start taking a write lock.
    status = _function(source, "audit_status", "audit_test")
    assert "for_update=True" not in status


def test_audit_test_holds_group_lock_through_side_effect_then_releases_before_ack() -> None:
    source = (HANDLERS / "audit.py").read_text(encoding="utf-8")
    test = _function(source, "audit_test")

    lock_auth = test.index("owner_group(message, bot, session, for_update=True)")
    telegram = test.index("await bot.send_message", lock_auth)
    release = test.index("await session.commit()", telegram)
    acknowledgement = test.index('await message.reply("Тестовое сообщение отправлено.")', release)
    assert lock_auth < telegram < release < acknowledgement
