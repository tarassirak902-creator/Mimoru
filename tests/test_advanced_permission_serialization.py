from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source() -> str:
    return (ROOT / "app/handlers/advanced.py").read_text(encoding="utf-8")


def _handler(source: str, name: str) -> str:
    body = source.split(f"async def {name}(", 1)[1]
    return body.split("@router.", 1)[0]


def test_telegram_permission_mutations_use_locked_owner_boundary() -> None:
    source = _source()
    for name in ("lockdown_on", "lockdown_off", "night_mode_off"):
        body = _handler(source, name)
        locked = body.index("await _owner_group(message, bot, session, for_update=True)")
        effect = body.index("await bot.set_chat_permissions(")
        commit = body.index("await session.commit()")
        assert locked < effect < commit


def test_permission_status_reads_remain_non_locking() -> None:
    source = _source()
    for name in ("lockdown_status", "night_mode_status"):
        body = _handler(source, name)
        assert "for_update=True" not in body


def test_night_mode_enable_remains_locked() -> None:
    body = _handler(_source(), "night_mode_on")
    assert "await _owner_group(message, bot, session, for_update=True)" in body
