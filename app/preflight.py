from __future__ import annotations

import asyncio
import sys

from redis.asyncio import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine


async def run_preflight() -> None:
    """Check configuration and infrastructure without contacting Telegram."""
    settings = get_settings()
    if not settings.bot_token or ":" not in settings.bot_token:
        raise RuntimeError("BOT_TOKEN is missing or has an invalid format")

    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        if not await redis.ping():
            raise RuntimeError("Redis PING returned a false result")
    finally:
        await redis.aclose()


async def _main() -> int:
    try:
        await run_preflight()
    except Exception as exc:
        print(f"Preflight failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()
    print("Preflight passed: configuration, PostgreSQL and Redis are available.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
