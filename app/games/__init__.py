from app.games.registry import game_registry
from app.games.mafia import MafiaGame, mafia_definition
from app.games.spy import SpyGame, spy_definition
from app.games.quiz import QuizGame, quiz_definition
from app.games.battleship import BattleshipGame, battleship_definition
from app.games.roulette import RouletteGame, roulette_definition
from app.games.crocodile import CrocodileGame, crocodile_definition
from app.games.cards import CardsGame, cards_definition
from app.games.arena import ArenaGame, arena_definition
from app.games.words import WordsGame, words_definition
from app.games.detective import DetectiveGame, detective_definition


def register_builtin_games() -> None:
    if game_registry.get(mafia_definition.code) is None:
        game_registry.register(mafia_definition, MafiaGame())
    if game_registry.get(spy_definition.code) is None:
        game_registry.register(spy_definition, SpyGame())
    if game_registry.get(quiz_definition.code) is None:
        game_registry.register(quiz_definition, QuizGame())
    if game_registry.get(battleship_definition.code) is None:
        game_registry.register(battleship_definition, BattleshipGame())
    if game_registry.get(roulette_definition.code) is None:
        game_registry.register(roulette_definition, RouletteGame())
    if game_registry.get(crocodile_definition.code) is None:
        game_registry.register(crocodile_definition, CrocodileGame())
    if game_registry.get(cards_definition.code) is None:
        game_registry.register(cards_definition, CardsGame())
    if game_registry.get(arena_definition.code) is None:
        game_registry.register(arena_definition, ArenaGame())
    if game_registry.get(words_definition.code) is None:
        game_registry.register(words_definition, WordsGame())
    if game_registry.get(detective_definition.code) is None:
        game_registry.register(detective_definition, DetectiveGame())


register_builtin_games()

__all__ = ["game_registry", "register_builtin_games"]
