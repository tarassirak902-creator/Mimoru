from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_target_status_forbidden_fails_closed() -> None:
    source = (ROOT / "app/services/permissions.py").read_text(encoding="utf-8")
    function = source.split("async def target_is_protected", 1)[1]
    assert "except TelegramForbiddenError:" in function
    assert "return True" in function


def test_bad_request_remains_caller_specific_for_departed_users() -> None:
    permissions = (ROOT / "app/services/permissions.py").read_text(encoding="utf-8")
    function = permissions.split("async def target_is_protected", 1)[1]
    assert "except TelegramBadRequest" not in function

    member_center = (ROOT / "app/handlers/member_center.py").read_text(encoding="utf-8")
    member_flow = member_center.split("async def member_punish", 1)[1].split("async def member_action", 1)[0]
    assert "except TelegramBadRequest:" in member_flow
    assert 'if action not in {"ban"}:' in member_flow


def test_execute_unmanaged_admin_lookup_fails_closed_on_forbidden() -> None:
    moderation = (ROOT / "app/services/moderation.py").read_text(encoding="utf-8")
    function = moderation.split("async def _unmanaged_telegram_admin", 1)[1].split("async def execute", 1)[0]
    assert "except (TelegramBadRequest, TelegramForbiddenError)" not in function
    assert "except TelegramForbiddenError:\n        return True" in function
    assert "except TelegramBadRequest:\n        return False" in function
