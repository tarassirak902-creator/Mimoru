from __future__ import annotations

from aiogram import Router

from app import game_friendly_history, game_friendly_results, group_help_full
from app.games import handlers as game_handlers
from app.games.mafia import handlers as mafia_handlers


router = Router(name=__name__)
_INCLUDED_CALLBACK_FAMILIES = ("gm", "fsfriendly", "fshfriendly")
router.include_router(mafia_handlers.router)
router.include_router(game_handlers.router)
router.include_router(group_help_full.router)
router.include_router(game_friendly_results.router)
router.include_router(game_friendly_history.router)
