from app.games.registry import game_registry
from app.games.mafia import MafiaGame, mafia_definition
from app.games.spy import SpyGame, spy_definition
from app.games.quiz import QuizGame, quiz_definition
from app.games.battleship import BattleshipGame, battleship_definition
from app.games.roulette import RouletteGame, roulette_definition
from app.games.crocodile import CrocodileGame, crocodile_definition
from app.games.cards import CardsGame, cards_definition
from app.games.arena import ArenaGame, arena_definition


def register_builtin_games() -> None:
    for definition, engine in (
        (mafia_definition, MafiaGame()), (spy_definition, SpyGame()), (quiz_definition, QuizGame()),
        (battleship_definition, BattleshipGame()), (roulette_definition, RouletteGame()),
        (crocodile_definition, CrocodileGame()), (cards_definition, CardsGame()), (arena_definition, ArenaGame()),
    ):
        if game_registry.get(definition.code) is None:
            game_registry.register(definition, engine)


register_builtin_games()

__all__ = ["game_registry", "register_builtin_games"]
