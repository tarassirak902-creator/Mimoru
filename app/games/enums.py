from __future__ import annotations

from enum import StrEnum


class GameSessionStatus(StrEnum):
    LOBBY = "lobby"
    RUNNING = "running"
    RECOVERING = "recovering"
    FINISHED = "finished"
    CANCELLED = "cancelled"
    BROKEN = "broken"


ACTIVE_SESSION_STATUSES = frozenset({
    GameSessionStatus.LOBBY.value,
    GameSessionStatus.RUNNING.value,
    GameSessionStatus.RECOVERING.value,
})
