from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GameDefinition:
    code: str
    title: str
    min_players: int
    max_players: int
    exclusive_group_game: bool = True
    supports_rating: bool = True
    supports_spectators: bool = False
    uses_private_mapping: bool = False
    default_timeout_seconds: int = 60

    def __post_init__(self) -> None:
        if not self.code or len(self.code) > 32:
            raise ValueError("game code must be 1..32 characters")
        if self.min_players < 1:
            raise ValueError("min_players must be positive")
        if self.max_players < self.min_players:
            raise ValueError("max_players must be >= min_players")
        if self.default_timeout_seconds < 1:
            raise ValueError("default timeout must be positive")
