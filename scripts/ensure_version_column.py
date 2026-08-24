"""Ensure alembic_version.version_num is wide enough for long revision IDs.

Alembic <1.13 creates version_num as VARCHAR(32). Some revisions in this
project exceed that limit. This script widens the column to VARCHAR(255)
if needed — safe, idempotent, and runs before ``alembic upgrade head``.
"""

import os


def main() -> None:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("[ensure_version_column] DATABASE_URL not set, skipping")
        return

    try:
        import asyncpg
        import asyncio
    except ImportError:
        print("[ensure_version_column] asyncpg not installed, skipping")
        return

    async_dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)

    async def _patch() -> None:
        conn = await asyncpg.connect(async_dsn)
        try:
            current = await conn.fetchval(
                "SELECT character_maximum_length "
                "FROM information_schema.columns "
                "WHERE table_name = 'alembic_version' AND column_name = 'version_num'"
            )
            if current is None:
                await conn.execute(
                    "CREATE TABLE IF NOT EXISTS alembic_version "
                    "(version_num VARCHAR(255) NOT NULL)"
                )
                print("[ensure_version_column] created alembic_version with VARCHAR(255)")
                return
            if current >= 255:
                print(f"[ensure_version_column] version_num is VARCHAR({current}), no action needed")
                return
            print(f"[ensure_version_column] version_num is VARCHAR({current}), widening to VARCHAR(255)")
            await conn.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)")
            print("[ensure_version_column] done")
        finally:
            await conn.close()

    asyncio.run(_patch())


if __name__ == "__main__":
    main()
