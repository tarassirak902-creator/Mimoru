from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GamePlayer, GameSession
from app.db.models import Group
from app.games.enums import ACTIVE_SESSION_STATUSES, GameSessionStatus
from app.games.registry import GameRegistry, game_registry


class GameConflictError(RuntimeError):
    pass


class GameNotFoundError(RuntimeError):
    pass


class GamePlayerError(RuntimeError):
    pass


class GameManager:
    def __init__(self, registry: GameRegistry | None = None) -> None:
        self.registry = registry or game_registry

    async def get_active_game(
        self,
        session: AsyncSession,
        *,
        group_id: int,
        for_update: bool = False,
    ) -> GameSession | None:
        query = (
            select(GameSession)
            .where(
                GameSession.group_id == group_id,
                GameSession.status.in_(ACTIVE_SESSION_STATUSES),
            )
            .order_by(GameSession.id.desc())
            .limit(1)
        )
        if for_update:
            query = query.with_for_update()
        return await session.scalar(query)

    async def create_lobby(
        self,
        session: AsyncSession,
        *,
        telegram_chat_id: int,
        game_type: str,
        creator_telegram_id: int,
        creator_display_name: str,
    ) -> GameSession:
        definition = self.registry.require(game_type)
        group = await session.scalar(
            select(Group)
            .where(
                Group.telegram_chat_id == telegram_chat_id,
                Group.is_active.is_(True),
            )
            .with_for_update()
        )
        if group is None:
            raise GameNotFoundError("active group not found")

        current = await self.get_active_game(session, group_id=group.id, for_update=True)
        if current is not None:
            raise GameConflictError(current.game_type)

        game = GameSession(
            group_id=group.id,
            game_type=definition.code,
            status=GameSessionStatus.LOBBY.value,
            phase="lobby",
            phase_seq=0,
            round_no=0,
            creator_telegram_id=creator_telegram_id,
            exclusive_group_game=definition.exclusive_group_game,
            state_json={},
        )
        session.add(game)
        try:
            await session.flush()
        except IntegrityError as error:
            await session.rollback()
            raise GameConflictError("active game already exists") from error

        session.add(
            GamePlayer(
                game_id=game.id,
                user_telegram_id=creator_telegram_id,
                display_name=creator_display_name,
                status="joined",
                state_json={},
            )
        )
        await session.commit()
        await session.refresh(game)
        return game

    async def join_lobby(
        self,
        session: AsyncSession,
        *,
        game_id: int,
        user_telegram_id: int,
        display_name: str,
    ) -> GamePlayer:
        game = await session.scalar(
            select(GameSession)
            .where(GameSession.id == game_id)
            .with_for_update()
        )
        if game is None:
            raise GameNotFoundError("game not found")
        if game.status != GameSessionStatus.LOBBY.value:
            raise GamePlayerError("lobby is closed")

        definition = self.registry.require(game.game_type)
        players = list(
            (
                await session.scalars(
                    select(GamePlayer)
                    .where(
                        GamePlayer.game_id == game.id,
                        GamePlayer.status == "joined",
                    )
                    .order_by(GamePlayer.id)
                    .with_for_update()
                )
            ).all()
        )
        existing = next((p for p in players if p.user_telegram_id == user_telegram_id), None)
        if existing is not None:
            return existing
        if len(players) >= definition.max_players:
            raise GamePlayerError("lobby is full")

        player = GamePlayer(
            game_id=game.id,
            user_telegram_id=user_telegram_id,
            display_name=display_name,
            status="joined",
            state_json={},
        )
        session.add(player)
        try:
            await session.commit()
        except IntegrityError as error:
            await session.rollback()
            existing = await session.scalar(
                select(GamePlayer).where(
                    GamePlayer.game_id == game.id,
                    GamePlayer.user_telegram_id == user_telegram_id,
                )
            )
            if existing is not None:
                return existing
            raise GamePlayerError("failed to join lobby") from error
        await session.refresh(player)
        return player

    async def leave_lobby(
        self,
        session: AsyncSession,
        *,
        game_id: int,
        user_telegram_id: int,
    ) -> None:
        game = await session.scalar(
            select(GameSession)
            .where(GameSession.id == game_id)
            .with_for_update()
        )
        if game is None:
            raise GameNotFoundError("game not found")
        if game.status != GameSessionStatus.LOBBY.value:
            raise GamePlayerError("lobby is closed")
        if game.creator_telegram_id == user_telegram_id:
            raise GamePlayerError("lobby creator cannot leave; cancel the lobby")

        player = await session.scalar(
            select(GamePlayer)
            .where(
                GamePlayer.game_id == game.id,
                GamePlayer.user_telegram_id == user_telegram_id,
                GamePlayer.status == "joined",
            )
            .with_for_update()
        )
        if player is None:
            return
        player.status = "left"
        await session.commit()

    async def player_count(self, session: AsyncSession, *, game_id: int) -> int:
        players = await session.scalars(
            select(GamePlayer.id).where(
                GamePlayer.game_id == game_id,
                GamePlayer.status == "joined",
            )
        )
        return len(players.all())
