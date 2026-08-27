from __future__ import annotations

from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GameSession
from app.games.config import GameDefinition


class BaseGame(ABC):
    definition: GameDefinition

    @abstractmethod
    async def start(self, session: AsyncSession, game: GameSession) -> None:
        raise NotImplementedError

    @abstractmethod
    async def handle_action(
        self,
        session: AsyncSession,
        game: GameSession,
        *,
        actor_telegram_id: int,
        action: str,
        value: int | str | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def handle_timeout(self, session: AsyncSession, game: GameSession) -> None:
        raise NotImplementedError

    @abstractmethod
    async def restore(self, session: AsyncSession, game: GameSession) -> None:
        raise NotImplementedError
