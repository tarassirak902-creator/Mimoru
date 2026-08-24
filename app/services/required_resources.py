from __future__ import annotations

import re
from urllib.parse import urlparse

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError


_TELEGRAM_HOSTS = {"t.me", "telegram.me", "www.t.me", "www.telegram.me"}
_USERNAME_RE = re.compile(r"[A-Za-z0-9_]{4,64}")
_INVITE_PATH_RE = re.compile(r"^\+[A-Za-z0-9_-]{1,64}$")


def normalize_public_telegram_resource(raw: str) -> str | None:
    """Return a canonical @username for a public Telegram group/channel link.

    Private invite links are intentionally rejected because Mimoru cannot
    reliably use them for membership checks by username.
    """
    value = raw.strip()
    if value.startswith("@"):
        username = value[1:]
    else:
        prepared = value if "://" in value else "https://" + value
        parsed = urlparse(prepared)
        if parsed.netloc.casefold() not in _TELEGRAM_HOSTS:
            return None
        path = parsed.path.strip("/")
        if not path or path.startswith("+") or "/" in path:
            return None
        username = path
    if not _USERNAME_RE.fullmatch(username):
        return None
    return "@" + username.casefold()


def validate_invite_link(url: str) -> str | None:
    """Return a Telegram invite link URL if it is valid, else None."""
    value = url.strip()
    if not value.startswith("https://"):
        value = "https://" + value
    parsed = urlparse(value)
    if parsed.netloc.casefold() not in _TELEGRAM_HOSTS:
        return None
    path = parsed.path.strip("/")
    if not path or not path.startswith("+") or "/" in path:
        return None
    if not _INVITE_PATH_RE.fullmatch(path):
        return None
    return f"https://t.me/{path}"


async def resolve_channel_url(bot: Bot, channel: str) -> str | None:
    """Resolve a channel identifier to a clickable Telegram navigation URL.

    The *channel* argument may be an ``@username``, a numeric chat ID (as
    string), or any other value stored in ``RequiredChannel.channel_username``.

    Resolution order:
    1. If *channel* starts with ``@``, it is already a public username –
       build ``https://t.me/<username>`` directly.
    2. Otherwise, attempt ``bot.get_chat(channel)`` to fetch live metadata.
       a. If the chat has a ``username``, use ``https://t.me/<username>``.
       b. If the chat has an ``invite_link``, use it.
    3. If resolution fails (bot lacks access, chat is private with no
       invite link, etc.), return ``None`` so the caller can skip the button
       rather than creating a broken URL.
    """
    if channel.startswith("@"):
        return f"https://t.me/{channel[1:]}"

    if "t.me/+" in channel or channel.startswith("https://t.me/+"):
        return channel if channel.startswith("https://") else f"https://{channel}"

    try:
        chat = await bot.get_chat(channel)
    except (TelegramBadRequest, TelegramForbiddenError, ValueError):
        return None

    if getattr(chat, "username", None):
        return f"https://t.me/{chat.username}"
    if getattr(chat, "invite_link", None):
        return chat.invite_link
    return None
