from __future__ import annotations

_DELETED_NAMES = {"deleted account", "удалённый аккаунт", "удаленный аккаунт"}


def is_deleted_profile(tg_user) -> bool:
    """Conservatively identify the profile shape Telegram uses for deleted accounts."""
    if tg_user is None or getattr(tg_user, "is_bot", False):
        return False
    first_name = (getattr(tg_user, "first_name", "") or "").strip().casefold()
    username = getattr(tg_user, "username", None)
    return not username and first_name in _DELETED_NAMES
