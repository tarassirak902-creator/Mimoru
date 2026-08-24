from __future__ import annotations

from app.db.moderation_operation_models import ModerationOperationIntent
from app.db.session import engine


async def ensure_moderation_operation_schema() -> None:
    """Create the moderation intent table for deployments without an Alembic startup step."""
    async with engine.begin() as connection:
        await connection.run_sync(ModerationOperationIntent.__table__.create, checkfirst=True)
