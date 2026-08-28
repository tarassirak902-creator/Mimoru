from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import StrEnum
import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GamePlayer, GameSession
from app.games.base import BaseGame
from app.games.config import GameDefinition


class MafiaPhase(StrEnum):
    ROLE_ASSIGNMENT = "role_assignment"
    DAY_START = "day_start"
    DISCUSSION = "discussion"
    DAY_VOTING = "day_voting"
    VOTING_RESULT = "voting_result"
    NIGHT_START = "night_start"
    NIGHT_ACTIONS = "night_actions"
    NIGHT_RESULT = "night_result"
    FINISHED = "finished"


mafia_definition = GameDefinition(
    code="mafia",
    title="🐺 Мафия",
    min_players=4,
    max_players=15,
    exclusive_group_game=True,
    supports_rating=True,
    supports_spectators=False,
    uses_private_mapping=True,
    default_timeout_seconds=60,
)


class MafiaGame(BaseGame):
    definition = mafia_definition

    async def _players(self, session: AsyncSession, game: GameSession) -> list[GamePlayer]:
        return list((await session.scalars(
            select(GamePlayer)
            .where(GamePlayer.game_id == game.id, GamePlayer.status.in_(("joined", "alive")))
            .order_by(GamePlayer.id)
            .with_for_update()
        )).all())

    @staticmethod
    def _role_deck(count: int) -> list[str]:
        mafia_count = max(1, count // 4)
        roles = ["mafia"] * mafia_count
        if count >= 4:
            roles.append("doctor")
        if count >= 5:
            roles.append("commissioner")
        roles.extend(["civilian"] * (count - len(roles)))
        random.SystemRandom().shuffle(roles)
        return roles

    async def start(self, session: AsyncSession, game: GameSession) -> None:
        game = await session.scalar(select(GameSession).where(GameSession.id == game.id).with_for_update())
        if game is None:
            return
        players = await self._players(session, game)
        if len(players) < self.definition.min_players:
            raise ValueError("not enough players for mafia")
        roles = self._role_deck(len(players))
        for player, role in zip(players, roles, strict=True):
            player.role = role
            player.team = "mafia" if role == "mafia" else "town"
            player.status = "alive"
            player.state_json = {"role_revealed": False}
        game.phase = MafiaPhase.DAY_START.value
        game.phase_seq += 1
        game.round_no = 1
        game.state_json = {
            "day": 1,
            "doctor_can_self_heal": True,
            "doctor_can_heal_same_player_twice": False,
            "last_healed_user_id": None,
        }
        game.deadline_at = datetime.now(timezone.utc) + timedelta(seconds=15)
        await session.commit()

    async def handle_action(
        self,
        session: AsyncSession,
        game: GameSession,
        *,
        actor_telegram_id: int,
        action: str,
        value: int | str | None = None,
    ) -> None:
        # Concrete voting/night actions are added in the next slice. Keeping this
        # strict prevents accidental text-driven gameplay or unsupported actions.
        raise ValueError(f"unsupported mafia action: {action}")

    async def handle_timeout(self, session: AsyncSession, game: GameSession) -> None:
        game = await session.scalar(select(GameSession).where(GameSession.id == game.id).with_for_update())
        if game is None or game.status != "running":
            return
        now = datetime.now(timezone.utc)
        if game.phase == MafiaPhase.DAY_START.value:
            game.phase = MafiaPhase.DISCUSSION.value
            game.phase_seq += 1
            game.deadline_at = now + timedelta(seconds=90)
        elif game.phase == MafiaPhase.DISCUSSION.value:
            game.phase = MafiaPhase.DAY_VOTING.value
            game.phase_seq += 1
            game.deadline_at = now + timedelta(seconds=60)
        elif game.phase == MafiaPhase.DAY_VOTING.value:
            game.phase = MafiaPhase.VOTING_RESULT.value
            game.phase_seq += 1
            game.deadline_at = now + timedelta(seconds=10)
        elif game.phase == MafiaPhase.VOTING_RESULT.value:
            game.phase = MafiaPhase.NIGHT_START.value
            game.phase_seq += 1
            game.deadline_at = now + timedelta(seconds=10)
        elif game.phase == MafiaPhase.NIGHT_START.value:
            game.phase = MafiaPhase.NIGHT_ACTIONS.value
            game.phase_seq += 1
            game.deadline_at = now + timedelta(seconds=60)
        elif game.phase == MafiaPhase.NIGHT_ACTIONS.value:
            game.phase = MafiaPhase.NIGHT_RESULT.value
            game.phase_seq += 1
            game.deadline_at = now + timedelta(seconds=10)
        elif game.phase == MafiaPhase.NIGHT_RESULT.value:
            game.round_no += 1
            state = dict(game.state_json or {})
            state["day"] = int(state.get("day", 1)) + 1
            game.state_json = state
            game.phase = MafiaPhase.DAY_START.value
            game.phase_seq += 1
            game.deadline_at = now + timedelta(seconds=15)
        await session.commit()

    async def restore(self, session: AsyncSession, game: GameSession) -> None:
        # State is durable. Recovery only repairs a missing deadline so the
        # scheduler can resume the state machine after a process restart.
        game = await session.scalar(select(GameSession).where(GameSession.id == game.id).with_for_update())
        if game is None or game.status != "running":
            return
        if game.deadline_at is None:
            game.deadline_at = datetime.now(timezone.utc) + timedelta(
                seconds=self.definition.default_timeout_seconds
            )
            await session.commit()
