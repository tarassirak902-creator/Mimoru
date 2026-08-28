from app.games.registry import game_registry
from app.games.mafia import MafiaGame, mafia_definition


def register_builtin_games() -> None:
    if game_registry.get(mafia_definition.code) is None:
        game_registry.register(mafia_definition, MafiaGame())


register_builtin_games()

__all__ = ["game_registry", "register_builtin_games"]
