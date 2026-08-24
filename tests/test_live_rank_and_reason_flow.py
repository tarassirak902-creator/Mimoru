from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_direct_warn_mute_ban_are_intercepted_before_legacy_execution() -> None:
    main = _source("app/main.py")
    guard = _source("app/handlers/kick_retirement.py")

    assert main.index("kick_retirement.router") < main.index("moderation_durable_guard.router")
    assert 'F.text.regexp(r"(?i)^(?:пред|мут|бан)(?:\\s|$)")' in guard
    handler = guard.split("async def moderation_reason_entry", 1)[1].split(
        "@router.callback_query", 1
    )[0]
    assert "parse_command" in handler
    assert "await redis.setex" in handler
    assert "moderation_duration_picker" in handler
    assert "await active_reasons" in handler
    assert "moderation_reason_picker" in handler
    assert "execute(" not in handler


def test_existing_unmanaged_telegram_admin_is_attached_without_promote_rewrite() -> None:
    source = _source("app/handlers/rank_provisioning_handlers.py")
    helper = source.split("async def _attach_existing_unmanaged_telegram_admin", 1)[1].split(
        "@router.callback_query", 1
    )[0]
    apply = source.split("async def safe_admin_access_apply", 1)[1].split(
        "@router.callback_query(F.data.regexp(r\"^rank_change", 1
    )[0]

    assert "member.status != ChatMemberStatus.ADMINISTRATOR" in helper
    assert "assignment.telegram_admin_managed" in helper
    assert "assignment.telegram_admin_managed = False" in helper
    assert '"telegram_rights_preserved": True' in helper
    assert "promote_chat_member" not in helper
    assert "_attach_existing_unmanaged_telegram_admin" in apply
    assert apply.index("_attach_existing_unmanaged_telegram_admin") < apply.index("provision_assignment")


def test_bot_only_demotion_failure_explains_correct_mode() -> None:
    source = _source("app/handlers/rank_provisioning_handlers.py")
    assert "Вы выбрали режим «Только Mimoru»" in source
    assert "выберите «Telegram + Mimoru»" in source
