from __future__ import annotations

from aiogram import Router

from app import game_friendly_history, game_friendly_results, group_help_full
from app.games import handlers as game_handlers
from app.games import settings_handlers as game_settings_handlers
from app.games import text_entry as game_text_entry
from app.games.battleship import handlers as battleship_handlers
from app.games.mafia import handlers as mafia_handlers
from app.games.quiz import handlers as quiz_handlers
from app.games.spy import handlers as spy_handlers


router = Router(name=__name__)
_INCLUDED_CALLBACK_FAMILIES = ("gm", "fsfriendly", "fshfriendly")
router.include_router(mafia_handlers.router)
router.include_router(spy_handlers.router)
router.include_router(quiz_handlers.router)
router.include_router(battleship_handlers.router)
router.include_router(game_text_entry.router)
router.include_router(game_settings_handlers.router)
router.include_router(game_handlers.router)
router.include_router(group_help_full.router)
router.include_router(game_friendly_results.router)
router.include_router(game_friendly_history.router)
