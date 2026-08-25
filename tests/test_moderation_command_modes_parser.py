from types import SimpleNamespace

from app.handlers.moderation_command_modes import _split_command, _structural_args_only


def _message(*, reply: bool):
    replied_user = SimpleNamespace(id=123) if reply else None
    replied_message = SimpleNamespace(from_user=replied_user) if reply else None
    return SimpleNamespace(reply_to_message=replied_message)


def test_reason_is_only_taken_from_second_line() -> None:
    command, args, reason = _split_command("Пред\nНеадекват")
    assert command == "пред"
    assert args == []
    assert reason == "Неадекват"


def test_mute_keeps_target_and_duration_on_first_line() -> None:
    command, args, reason = _split_command("Мут @user 2ч\nФлуд")
    assert command == "мут"
    assert args == ["@user", "2ч"]
    assert reason == "Флуд"


def test_inline_words_are_not_a_reason() -> None:
    command, args, reason = _split_command("Пред неадекват")
    assert command == "пред"
    assert args == ["неадекват"]
    assert reason == ""
    assert _structural_args_only(_message(reply=True), args) == []


def test_first_line_keeps_only_target_and_duration() -> None:
    args = ["@user", "2ч", "неадекват"]
    assert _structural_args_only(_message(reply=False), args) == ["@user", "2ч"]
