from __future__ import annotations

import asyncio

from aiogram import Bot


# Compatibility background entrypoint. Old automatic pseudo-games were retired
# when entertainment was separated from the real games domain. The main loop may
# keep creating this task safely until the new games subsystem replaces it.
async def run_fun_auto_activity(bot: Bot) -> None:
    return None


async def fun_background_loop(bot: Bot, stop_event: asyncio.Event) -> None:
    await stop_event.wait()
