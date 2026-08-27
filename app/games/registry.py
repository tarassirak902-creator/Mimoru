from __future__ import annotations

from dataclasses import dataclass

from app.games.base import BaseGame
from app.games.config import GameDefinition


@dataclass(frozen=True, slots=True)
class GameEntry:
    definition: GameDefinition
    engine: BaseGame


class GameRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, GameEntry] = {}

    def register(self, definition: GameDefinition, engine: BaseGame) -> None:
        if definition.code in self._entries:
            raise ValueError(f"game already registered: {definition.code}")
        if engine.definition.code != definition.code:
            raise ValueError("game engine definition does not match registry definition")
        self._entries[definition.code] = GameEntry(definition=definition, engine=engine)

    def get_entry(self, code: str) -> GameEntry | None:
        return self._entries.get(code)

    def require_entry(self, code: str) -> GameEntry:
        entry = self.get_entry(code)
        if entry is None:
            raise KeyError(code)
        return entry

    def get(self, code: str) -> GameDefinition | None:
        entry = self.get_entry(code)
        return entry.definition if entry is not None else None

    def require(self, code: str) -> GameDefinition:
        return self.require_entry(code).definition

    def engine(self, code: str) -> BaseGame:
        return self.require_entry(code).engine

    def all(self) -> tuple[GameDefinition, ...]:
        return tuple(entry.definition for entry in self._entries.values())


game_registry = GameRegistry()
