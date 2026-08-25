from app.handlers import group_commands, kick_retirement, moderation_command_modes, moderation_durable_guard


def _handler_names(router) -> list[str]:
    return [getattr(handler.callback, "__name__", "") for handler in router.message.handlers]


def test_warn_mute_ban_have_one_physical_message_entrypoint() -> None:
    assert "moderation_command_mode" in _handler_names(moderation_command_modes.router)
    assert "direct_reply_moderation" not in _handler_names(group_commands.router)
    assert "durable_direct_reply" not in _handler_names(moderation_durable_guard.router)
    assert "moderation_reason_entry" not in _handler_names(kick_retirement.router)


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
