from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _body(source: str, name: str) -> str:
    return source.split(f"async def {name}(", 1)[1].split("@router.message", 1)[0]


def test_safety_mutations_use_locked_owner_boundary() -> None:
    source = (ROOT / "app/handlers/safety.py").read_text(encoding="utf-8")
    assert "managed_group_for_message" in source
    for name in ("trust_user", "untrust_user", "toggle_antiraid", "configure_antiraid", "warning_expiry"):
        body = _body(source, name)
        assert "for_update=True" in body
        assert body.index("for_update=True") < body.index("await session.commit()")
    assert "for_update=True" not in _body(source, "trusted_users")


def test_hardening_mutations_use_locked_owner_boundary() -> None:
    source = (ROOT / "app/handlers/hardening.py").read_text(encoding="utf-8")
    assert "managed_group_for_message" in source
    for name in ("allow_link", "disallow_link", "resolve_complaint"):
        body = _body(source, name)
        assert "for_update=True" in body
        assert body.index("for_update=True") < body.index("await session.commit()")
    for name in ("allowed_links", "complaints"):
        assert "for_update=True" not in _body(source, name)


def test_shared_owner_boundary_locks_before_live_access_check() -> None:
    source = (ROOT / "app/services/owner_management.py").read_text(encoding="utf-8")
    assert source.index(".with_for_update()") < source.index("await can_manage_group(")
