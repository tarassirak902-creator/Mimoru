"""Tests for public_user_token usage in active modpending payloads."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(filename: str) -> str:
    return (ROOT / "app" / "handlers" / filename).read_text(encoding="utf-8")


def test_active_command_mode_uses_public_user_token_in_modpending_payload() -> None:
    source = _source("moderation_command_modes.py")
    assert "from app.services.public_identity import public_user_token" in source
    assert '"target_name": public_user_token(target_id)' in source
    assert '"moderator_name": public_user_token(message.from_user.id)' in source
    assert '"target_name": target.full_name' not in source
    assert '"moderator_name": message.from_user.full_name' not in source


def test_group_uses_public_user_token_in_modpending_payload() -> None:
    source = _source("group.py")
    assert "from app.services.public_identity import public_user_token" in source
    assert '"target_name": public_user_token(target.id)' in source
    assert '"moderator_name": public_user_token(message.from_user.id)' in source


def test_group_uses_public_user_token_in_reply_messages() -> None:
    source = _source("group.py")
    assert "public_user_token(target.id)" in source
    assert '"target_name": public_user_token(target.id)' in source


def test_retired_kick_module_no_longer_builds_modpending_payloads() -> None:
    source = _source("kick_retirement.py")
    assert "mimoru:modpending:" not in source
    assert "moderation_reason_entry" not in source


def test_member_center_uses_public_user_token_in_modpending() -> None:
    source = _source("member_center.py")
    assert '"target_name": target_name' in source
    assert "target_name = public_user_token(user_id)" in source
    assert '"moderator_name": public_user_token(callback.from_user.id)' in source
