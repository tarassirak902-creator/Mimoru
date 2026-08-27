from __future__ import annotations

from app.games.config import GameDefinition


class GameRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, GameDefinition] = {}

    def register(self, definition: GameDefinition) -> None:
        if definition.code in self._definitions:
            raise ValueError(f"game already registered: {definition.code}")
        self._definitions[definition.code] = definition

    def get(self, code: str) -> GameDefinition | None:
        return self._definitions.get(code)

    def require(self, code: str) -> GameDefinition:
        definition = self.get(code)
        if definition is None:
            raise KeyError(code)
        return definition

    def all(self) -> tuple[GameDefinition, ...]:
        return tuple(self._definitions.values())


game_registry = GameRegistry()
