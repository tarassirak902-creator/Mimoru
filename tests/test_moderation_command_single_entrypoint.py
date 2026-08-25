from app import main as app_main
from app.handlers import group_commands, moderation_command_modes, moderation_durable_guard


def _handler_names(router) -> list[str]:
    return [getattr(handler.callback, "__name__", "") for handler in router.message.handlers]


def test_single_entrypoint_cleanup_removes_legacy_handlers() -> None:
    group_handlers = list(group_commands.router.message.handlers)
    durable_handlers = list(moderation_durable_guard.router.message.handlers)
    try:
        assert "moderation_command_mode" in _handler_names(moderation_command_modes.router)
        assert "direct_reply_moderation" in _handler_names(group_commands.router)
        assert "durable_direct_reply" in _handler_names(moderation_durable_guard.router)

        app_main._disable_legacy_direct_moderation_handlers()

        assert "moderation_command_mode" in _handler_names(moderation_command_modes.router)
        assert "direct_reply_moderation" not in _handler_names(group_commands.router)
        assert "durable_direct_reply" not in _handler_names(moderation_durable_guard.router)
    finally:
        group_commands.router.message.handlers[:] = group_handlers
        moderation_durable_guard.router.message.handlers[:] = durable_handlers


def test_second_line_is_the_only_direct_reason() -> None:
    assert moderation_command_modes._split_command("Пред\nНеадекват") == (
        "пред",
        [],
        "Неадекват",
    )
    assert moderation_command_modes._split_command("Мут 2ч\nФлуд") == (
        "мут",
        ["2ч"],
        "Флуд",
    )
    assert moderation_command_modes._split_command("Пред неадекват") == (
        "пред",
        ["неадекват"],
        "",
    )
