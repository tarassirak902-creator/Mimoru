from __future__ import annotations

import re
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.methods.base import TelegramMethod
from aiogram.types import MessageEntity
from sqlalchemy import select

from app.db.models import User


_PUBLIC_ID_RE = re.compile(r"\bID\s+(\d{5,20})\b")
_PUBLIC_USER_TOKEN_RE = re.compile(r"\[\[mimoru-user:(\d{5,20})\]\]")


def public_user_token(user_id: int) -> str:
    """Return an internal placeholder for a user-facing Telegram mention.

    The placeholder is never intended to reach Telegram unchanged. PlainTextBot resolves it
    immediately before send/edit and turns it into a visible name plus a clickable text_link.
    Keeping only the numeric ID in the placeholder also means handlers do not have to carry
    stale display names around in durable state.
    """

    return f"[[mimoru-user:{int(user_id)}]]"


def _utf16_len(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def _visible_name(user: Any) -> str | None:
    # The public label should look like the person looks in Telegram. Prefer the profile
    # display name and only fall back to @username when no display name is available.
    full_name = (getattr(user, "full_name", None) or "").strip()
    if full_name:
        return full_name
    first_name = (getattr(user, "first_name", None) or "").strip()
    last_name = (getattr(user, "last_name", None) or "").strip()
    full_name = " ".join(part for part in (first_name, last_name) if part).strip()
    if full_name:
        return full_name
    username = getattr(user, "username", None)
    return f"@{username}" if username else None


async def _stored_visible_name(user_id: int) -> str | None:
    # Import lazily so importing this output helper in tests does not initialize
    # application settings (and require BOT_TOKEN) before the fallback is used.
    from app.db.session import SessionFactory

    async with SessionFactory() as session:
        user = await session.scalar(select(User).where(User.telegram_id == user_id))
    if user is None:
        return None
    full_name = " ".join(part for part in (user.first_name, user.last_name) if part).strip()
    if full_name:
        return full_name
    return f"@{user.username}" if user.username else None


async def _resolve_visible_name(bot: Bot, chat_id: int | str | None, user_id: int) -> str:
    # For real group/supergroup chat IDs prefer Telegram's current profile so renamed users are
    # displayed exactly as Telegram currently knows them. Private/panel messages cannot resolve a
    # third party with getChatMember, so they use Mimoru's last stored Telegram profile instead.
    if isinstance(chat_id, int) and chat_id < 0:
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            live = _visible_name(member.user)
            if live:
                return live
        except (TelegramBadRequest, TelegramForbiddenError):
            pass
    stored = await _stored_visible_name(user_id)
    return stored or "Пользователь"


def _replaceable_pattern(text: str, *, include_legacy_id: bool) -> re.Pattern[str] | None:
    has_token = _PUBLIC_USER_TOKEN_RE.search(text) is not None
    has_legacy = include_legacy_id and _PUBLIC_ID_RE.search(text) is not None
    if not has_token and not has_legacy:
        return None
    if has_token and has_legacy:
        return re.compile(r"\[\[mimoru-user:(\d{5,20})\]\]|\bID\s+(\d{5,20})\b")
    return _PUBLIC_USER_TOKEN_RE if has_token else _PUBLIC_ID_RE


async def _replace_text_identities(
    bot: Bot,
    *,
    chat_id: int | str | None,
    text: str,
    include_legacy_id: bool,
) -> tuple[str, list[MessageEntity]]:
    pattern = _replaceable_pattern(text, include_legacy_id=include_legacy_id)
    if pattern is None:
        return text, []

    chunks: list[str] = []
    entities: list[MessageEntity] = []
    cursor = 0
    for match in pattern.finditer(text):
        chunks.append(text[cursor:match.start()])
        raw_id = next((value for value in match.groups() if value is not None), None)
        if raw_id is None:
            cursor = match.end()
            continue
        user_id = int(raw_id)
        label = await _resolve_visible_name(bot, chat_id, user_id)

        prefix = "".join(chunks)
        chunks.append(label)
        entities.append(
            MessageEntity(
                type="text_link",
                offset=_utf16_len(prefix),
                length=_utf16_len(label),
                url=f"tg://user?id={user_id}",
            )
        )
        cursor = match.end()

    chunks.append(text[cursor:])
    return "".join(chunks), entities


async def replace_public_group_id_labels(bot: Bot, method: TelegramMethod[Any]) -> TelegramMethod[Any]:
    """Resolve internal user placeholders to clickable Telegram display names.

    Internal Telegram IDs remain untouched in callback_data, database fields and Telegram API
    arguments. Handlers should use ``public_user_token(user_id)`` whenever they render a person.

    Identity priority is current Telegram display name in a group, then Mimoru's last stored
    Telegram display name, with @username only as a fallback. Legacy ``ID 123...`` replacement is
    deliberately group-only because private admin screens can contain numeric operation/message IDs
    that are not user identities.
    """

    chat_id = getattr(method, "chat_id", None)
    include_legacy_id = isinstance(chat_id, int) and chat_id < 0
    updates: dict[str, Any] = {}

    text = getattr(method, "text", None)
    current_entities = getattr(method, "entities", None)
    if (
        isinstance(text, str)
        and not current_entities
        and _replaceable_pattern(text, include_legacy_id=include_legacy_id) is not None
    ):
        new_text, entities = await _replace_text_identities(
            bot,
            chat_id=chat_id,
            text=text,
            include_legacy_id=include_legacy_id,
        )
        updates["text"] = new_text
        if hasattr(method, "entities"):
            updates["entities"] = entities or None

    caption = getattr(method, "caption", None)
    current_caption_entities = getattr(method, "caption_entities", None)
    if (
        isinstance(caption, str)
        and not current_caption_entities
        and _replaceable_pattern(caption, include_legacy_id=include_legacy_id) is not None
    ):
        new_caption, caption_entities = await _replace_text_identities(
            bot,
            chat_id=chat_id,
            text=caption,
            include_legacy_id=include_legacy_id,
        )
        updates["caption"] = new_caption
        if hasattr(method, "caption_entities"):
            updates["caption_entities"] = caption_entities or None

    return method.model_copy(update=updates) if updates else method
