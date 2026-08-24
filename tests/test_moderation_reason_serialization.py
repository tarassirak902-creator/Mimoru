from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source() -> str:
    return (ROOT / "app/handlers/reason_admin.py").read_text(encoding="utf-8")


def _handler(source: str, name: str) -> str:
    body = source.split(f"async def {name}(", 1)[1]
    return body.split("@router.", 1)[0]


def test_owned_group_lock_is_opt_in() -> None:
    source = _source()
    helper = source.split("async def owned_group(", 1)[1].split("async def get_reason", 1)[0]
    assert "for_update: bool = False" in helper
    assert "if for_update:" in helper
    assert "q = q.with_for_update()" in helper


def test_reason_mutations_lock_before_durable_writes() -> None:
    source = _source()
    mutations = {
        "reasons": "await ensure_default_reasons(",
        "reason_add_text": "session.add(row)",
        "reason_action": "row.actions = actions",
        "reason_toggle": "row.active = not row.active",
        "reason_rename_text": "row.name = name",
        "reason_delete": "await session.delete(row)",
    }
    for name, mutation in mutations.items():
        body = _handler(source, name)
        lock = body.index("for_update=True")
        write = body.index(mutation)
        assert lock < write
        assert "await session.commit()" in body


def test_reason_navigation_remains_non_locking() -> None:
    source = _source()
    for name in ("reason_add", "reason_edit", "reason_rename", "reason_delete_ask", "moderation_help"):
        body = _handler(source, name)
        assert "for_update=True" not in body
