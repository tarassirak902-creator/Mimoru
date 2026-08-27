from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GameAction, GamePlayer, GameSession
from app.games.enums import GameSessionStatus
from app.games.targets import resolve_target_number


class GameActionError(RuntimeError):
    pass


async def record_numbered_action(
    session: AsyncSession,
    *,
    game_id: int,
    expected_phase_seq: int,
    actor_telegram_id: int,
    action_type: str,
    number: int,
    require_target_alive: bool = True,
) -> tuple[GameAction, bool]:
    game = await session.scalar(
        select(GameSession)
        .where(GameSession.id == game_id)
        .with_for_update()
    )
    if game is None:
        raise GameActionError("game not found")
    if game.status != GameSessionStatus.RUNNING.value:
        raise GameActionError("game is not running")
    if game.phase_seq != expected_phase_seq:
        raise GameActionError("phase is stale")

    actor = await session.scalar(
        select(GamePlayer)
        .where(
            GamePlayer.game_id == game.id,
            GamePlayer.user_telegram_id == actor_telegram_id,
        )
        .with_for_update()
    )
    if actor is None or actor.status not in {"joined", "alive"}:
        raise GameActionError("actor is not active player")

    existing = await session.scalar(
        select(GameAction)
        .where(
            GameAction.game_id == game.id,
            GameAction.phase_seq == game.phase_seq,
            GameAction.actor_telegram_id == actor_telegram_id,
            GameAction.action_type == action_type,
        )
        .with_for_update()
    )
    if existing is not None:
        return existing, False

    target_telegram_id = await resolve_target_number(
        session,
        game_id=game.id,
        phase_seq=game.phase_seq,
        actor_telegram_id=actor_telegram_id,
        number=number,
    )
    if target_telegram_id is None:
        raise GameActionError("target number is invalid")

    target = await session.scalar(
        select(GamePlayer)
        .where(
            GamePlayer.game_id == game.id,
            GamePlayer.user_telegram_id == target_telegram_id,
        )
        .with_for_update()
    )
    if target is None:
        raise GameActionError("target is not a player")
    if require_target_alive and target.status not in {"joined", "alive"}:
        raise GameActionError("target is not active")

    action = GameAction(
        game_id=game.id,
        round_no=game.round_no,
        phase_seq=game.phase_seq,
        actor_telegram_id=actor_telegram_id,
        action_type=action_type,
        target_telegram_id=target_telegram_id,
        payload_json={"number": number},
    )
    session.add(action)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await session.scalar(
            select(GameAction).where(
                GameAction.game_id == game.id,
                GameAction.phase_seq == expected_phase_seq,
                GameAction.actor_telegram_id == actor_telegram_id,
                GameAction.action_type == action_type,
            )
        )
        if existing is not None:
            return existing, False
        raise

    await session.refresh(action)
    return action, True
