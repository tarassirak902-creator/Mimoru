from pathlib import Path

from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import EditMessageReplyMarkup, EditMessageText, SendMessage

from app.main import _is_idempotent_edit_error as is_idempotent_edit_error


ROOT = Path(__file__).resolve().parents[1]


def _bad_request(message: str) -> TelegramBadRequest:
    return TelegramBadRequest(method=SendMessage(chat_id=1, text="x"), message=message)


def test_repeated_text_edit_is_idempotent() -> None:
    method = EditMessageText(chat_id=1, message_id=1, text="same")
    assert is_idempotent_edit_error(method, _bad_request("Bad Request: message is not modified"))


def test_repeated_markup_edit_is_idempotent() -> None:
    method = EditMessageReplyMarkup(chat_id=1, message_id=1)
    assert is_idempotent_edit_error(method, _bad_request("Bad Request: message is not modified"))


def test_other_bad_requests_are_not_swallowed() -> None:
    method = EditMessageText(chat_id=1, message_id=1, text="same")
    assert not is_idempotent_edit_error(method, _bad_request("Bad Request: message to edit not found"))


def test_non_edit_methods_are_not_swallowed() -> None:
    method = SendMessage(chat_id=1, text="x")
    assert not is_idempotent_edit_error(method, _bad_request("Bad Request: message is not modified"))


def test_runtime_bot_has_idempotent_edit_guard() -> None:
    source = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "except TelegramBadRequest as exc:" in source
    assert "_is_idempotent_edit_error(plain_method, exc)" in source
