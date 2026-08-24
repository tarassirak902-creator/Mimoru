from __future__ import annotations

import asyncio
from contextlib import suppress


async def stop_task(task: asyncio.Task[object] | None, timeout: float = 10.0) -> None:
    """Stop a background task without allowing shutdown to hang forever."""
    if task is None:
        return
    if task.done():
        with suppress(asyncio.CancelledError):
            await task
        return

    task.cancel()
    try:
        await asyncio.wait_for(task, timeout=timeout)
    except (asyncio.CancelledError, TimeoutError):
        return
