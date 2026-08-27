from __future__ import annotations

from aiogram import Router

from app.game_contracts import (
    HISTORY_COMMANDS,
    HISTORY_TITLES,
    HISTORY_WORDS,
    PROPOSALS,
    PROPOSAL_ACTIONS,
)

# Compatibility shim for older imports. Production social game handlers live in
# app.game_friendly_results and app.game_friendly_history, which are included by
# fun_preferences. Keeping an empty router here makes the existing main wiring
# harmless while avoiding a second implementation of the same commands.
router = Router(name=__name__)

__all__ = (
    "HISTORY_COMMANDS",
    "HISTORY_TITLES",
    "HISTORY_WORDS",
    "PROPOSALS",
    "PROPOSAL_ACTIONS",
    "router",
)
