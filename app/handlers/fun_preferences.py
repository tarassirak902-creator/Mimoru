from __future__ import annotations

from aiogram import Router

from app import game_friendly_history, game_friendly_results, group_help_full


router = Router(name=__name__)
_INCLUDED_CALLBACK_FAMILIES = ("fsfriendly", "fshfriendly")
router.include_router(group_help_full.router)
router.include_router(game_friendly_results.router)
router.include_router(game_friendly_history.router)
