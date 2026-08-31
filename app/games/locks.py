from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def advisory_xact_lock(
    session: AsyncSession,
    *,
    namespace: int,
    key: int,
) -> None:
    """Serialize a game-side effect on the current PostgreSQL transaction."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:namespace, :key)"),
        {"namespace": namespace, "key": key},
    )
