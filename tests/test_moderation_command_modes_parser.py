from types import SimpleNamespace

from app.handlers.moderation_command_modes import _split_command, _structural_args_only
from app.utils.duration import parse_duration


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


def test_mute_accepts_spaced_one_minute_duration() -> None:
    command, args, reason = _split_command("Мут 1 мин")
    assert command == "мут"
    assert args == ["1мин"]
    assert reason == ""
    assert parse_duration(args[0]) == 60
    assert _structural_args_only(_message(reply=True), args) == ["1мин"]


def test_mute_accepts_spaced_duration_with_target_and_reason() -> None:
    command, args, reason = _split_command("Мут @user 1 мин\nФлуд")
    assert command == "мут"
    assert args == ["@user", "1мин"]
    assert reason == "Флуд"
    assert _structural_args_only(_message(reply=False), args) == ["@user", "1мин"]


def test_mute_accepts_natural_russian_duration_words() -> None:
    for text, expected in (
        ("Мут 1 минута", "1мин"),
        ("Мут 2 минуты", "2мин"),
        ("Мут 5 минут", "5мин"),
        ("Мут 2 часа", "2час"),
        ("Мут 3 дня", "3дн"),
        ("Мут 2 недели", "2нед"),
    ):
        _, args, _ = _split_command(text)
        assert args == [expected]
        assert parse_duration(expected) is not None


def test_inline_words_are_not_a_reason() -> None:
    command, args, reason = _split_command("Пред неадекват")
    assert command == "пред"
    assert args == ["неадекват"]
    assert reason == ""
    assert _structural_args_only(_message(reply=True), args) == []


def test_first_line_keeps_only_target_and_duration() -> None:
    args = ["@user", "2ч", "неадекват"]
    assert _structural_args_only(_message(reply=False), args) == ["@user", "2ч"]
