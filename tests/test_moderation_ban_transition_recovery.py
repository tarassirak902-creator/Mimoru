from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_repeated_ban_recovery_requires_changed_telegram_expiry() -> None:
    source = (ROOT / "app/services/moderation_operations.py").read_text(encoding="utf-8")
    helper = source.split("def _ban_transition_proves_applied", 1)[1].split(
        "def _state_transition_proves_applied", 1
    )[0]
    assert 'payload.get("pre_banned")' in helper
    assert '_payload_time(payload, "pre_until")' in helper
    assert '_payload_time(payload, "ends_at")' in helper
    assert "current_until = _member_until(member)" in helper
    assert "current_matches and not pre_matches" in helper
    assert "pre_until is not None and current_until is None" in helper


def test_general_transition_proof_delegates_ban_to_expiry_aware_helper() -> None:
    source = (ROOT / "app/services/moderation_operations.py").read_text(encoding="utf-8")
    proof = source.split("def _state_transition_proves_applied", 1)[1].split(
        "async def _restore_orphan_rank", 1
    )[0]
    assert 'if intent.action == "ban":' in proof
    assert "return _ban_transition_proves_applied(member, payload)" in proof
