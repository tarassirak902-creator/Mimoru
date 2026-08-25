from types import SimpleNamespace

import pytest

from app.handlers.moderation_command_modes import ModerationCommandModeFilter, _split_command


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "пред",
        "Пред\nНеадекват",
        "мут @user 2ч\nОскорбления",
        "БАН 123456789\nПовторный спам",
        "   пред\nПричина",
    ],
)
async def test_moderation_command_filter_accepts_supported_commands(text: str) -> None:
    message = SimpleNamespace(text=text)
    assert await ModerationCommandModeFilter()(message) is True


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["преды", "разбан", "привет", "", None])
async def test_moderation_command_filter_rejects_other_messages(text: str | None) -> None:
    message = SimpleNamespace(text=text)
    assert await ModerationCommandModeFilter()(message) is False


def test_split_reply_style_direct_reason() -> None:
    command, args, reason = _split_command("Пред\nНеадекват")
    assert command == "пред"
    assert args == []
    assert reason == "Неадекват"


@pytest.mark.parametrize("separator", ["\n", "\r\n", "\r", "\x85", "\u2028", "\u2029"])
def test_split_reply_style_accepts_line_separators(separator: str) -> None:
    command, args, reason = _split_command(f"Пред{separator}В")
    assert command == "пред"
    assert args == []
    assert reason == "В"


def test_split_target_duration_and_multiline_reason() -> None:
    command, args, reason = _split_command("мут @BLACK_SFB 2ч\nОскорбления\nПовторное нарушение")
    assert command == "мут"
    assert args == ["@BLACK_SFB", "2ч"]
    assert reason == "Оскорбления\nПовторное нарушение"
