from pathlib import Path
from types import SimpleNamespace

import pytest
from aiogram.methods import SendMessage

import app.services.public_identity as public_identity
from app.services.public_identity import public_user_token, replace_public_group_id_labels


ROOT = Path(__file__).resolve().parents[1]


class _FakeBot:
    async def get_chat_member(self, chat_id: int, user_id: int):
        assert chat_id == -1001234567890
        assert user_id == 123456789
        return SimpleNamespace(
            user=SimpleNamespace(
                username="ivan_petrov",
                full_name="Иван Петров",
                first_name="Иван",
                last_name="Петров",
            )
        )


@pytest.mark.asyncio
async def test_group_id_label_becomes_clickable_display_name() -> None:
    method = SendMessage(
        chat_id=-1001234567890,
        text="⚠️ Участник: ID 123456789 · предупреждение",
    )

    updated = await replace_public_group_id_labels(_FakeBot(), method)

    # Display name wins over @username because users should look the same as in Telegram.
    assert updated.text == "⚠️ Участник: Иван Петров · предупреждение"
    assert "123456789" not in updated.text
    assert "@ivan_petrov" not in updated.text
    assert updated.entities is not None
    assert len(updated.entities) == 1
    assert updated.entities[0].url == "tg://user?id=123456789"


@pytest.mark.asyncio
async def test_private_technical_id_is_not_rewritten() -> None:
    method = SendMessage(chat_id=12345, text="Технический ID 123456789")
    updated = await replace_public_group_id_labels(_FakeBot(), method)
    assert updated.text == method.text
    assert updated.entities == method.entities


@pytest.mark.asyncio
async def test_private_user_token_uses_stored_name_and_is_clickable(monkeypatch) -> None:
    async def stored_name(user_id: int) -> str | None:
        assert user_id == 123456789
        return "Иван Петров"

    monkeypatch.setattr(public_identity, "_stored_visible_name", stored_name)
    method = SendMessage(
        chat_id=555000,
        text=f"На кого: {public_user_token(123456789)}",
    )

    updated = await replace_public_group_id_labels(_FakeBot(), method)

    assert updated.text == "На кого: Иван Петров"
    assert updated.entities is not None
    assert len(updated.entities) == 1
    assert updated.entities[0].url == "tg://user?id=123456789"


def test_public_user_token_keeps_id_internal() -> None:
    token = public_user_token(123456789)
    assert token == "[[mimoru-user:123456789]]"


def test_plain_text_bot_applies_public_identity_layer() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "replace_public_group_id_labels" in main
    assert "plain_method = await replace_public_group_id_labels(self, plain_method)" in main
