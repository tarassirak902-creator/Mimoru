from app.games.registry import game_registry
from app.games.mafia import MafiaGame, mafia_definition
from app.games.spy import SpyGame, spy_definition
from app.games.quiz import QuizGame, quiz_definition
from app.games.battleship import BattleshipGame, battleship_definition


def register_builtin_games() -> None:
    if game_registry.get(mafia_definition.code) is None:
        game_registry.register(mafia_definition, MafiaGame())
    if game_registry.get(spy_definition.code) is None:
        game_registry.register(spy_definition, SpyGame())
    if game_registry.get(quiz_definition.code) is None:
        game_registry.register(quiz_definition, QuizGame())
    if game_registry.get(battleship_definition.code) is None:
        game_registry.register(battleship_definition, BattleshipGame())


register_builtin_games()

__all__ = ["game_registry", "register_builtin_games"]
