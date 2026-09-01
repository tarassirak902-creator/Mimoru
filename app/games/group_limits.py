from __future__ import annotations

from app.db.game_models import GameGroupSettings
from app.games.config import GameDefinition


PLAYER_CAP_KEY = "max_players"
PLAYER_CAP_PRESETS = (4, 6, 8, 12, 20)


def configured_player_cap(settings: GameGroupSettings | None) -> int | None:
    if settings is None:
        return None
    raw = dict(settings.settings_json or {}).get(PLAYER_CAP_KEY)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 2 else None


def effective_max_players(
    definition: GameDefinition,
    settings: GameGroupSettings | None,
) -> int:
    cap = configured_player_cap(settings)
    if cap is None:
        return definition.max_players
    return max(definition.min_players, min(definition.max_players, cap))


def set_player_cap(settings: GameGroupSettings, value: int | None) -> None:
    data = dict(settings.settings_json or {})
    if value is None:
        data.pop(PLAYER_CAP_KEY, None)
    else:
        data[PLAYER_CAP_KEY] = max(2, int(value))
    settings.settings_json = data
