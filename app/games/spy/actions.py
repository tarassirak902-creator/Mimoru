from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GamePlayer, GameSession
from app.games.actions import GameActionError, record_numbered_action
from app.games.spy.game import SpyPhase
from app.games.targets import ensure_target_map, get_target_map


async def _active_player(
    session: AsyncSession,
    *,
    game_id: int,
    user_id: int,
) -> GamePlayer | None:
    return await session.scalar(
        select(GamePlayer).where(
            GamePlayer.game_id == game_id,
            GamePlayer.user_telegram_id == user_id,
            GamePlayer.status == "alive",
        )
    )


async def ensure_spy_vote_map(
    session: AsyncSession,
    *,
    game: GameSession,
    actor_user_id: int,
):
    if game.phase != SpyPhase.VOTING.value:
        raise GameActionError("voting is not active")
    actor = await _active_player(session, game_id=game.id, user_id=actor_user_id)
    if actor is None:
        raise GameActionError("actor is not active player")
    targets = list((await session.scalars(
        select(GamePlayer.user_telegram_id)
        .where(
            GamePlayer.game_id == game.id,
            GamePlayer.status == "alive",
            GamePlayer.user_telegram_id != actor_user_id,
        )
        .order_by(GamePlayer.id)
    )).all())
    return await ensure_target_map(
        session,
        game_id=game.id,
        phase_seq=game.phase_seq,
        actor_telegram_id=actor_user_id,
        target_telegram_ids=targets,
    )


async def spy_vote_map_lines(
    session: AsyncSession,
    *,
    game: GameSession,
    actor_user_id: int,
) -> list[str]:
    await ensure_spy_vote_map(session, game=game, actor_user_id=actor_user_id)
    rows = await get_target_map(
        session,
        game_id=game.id,
        phase_seq=game.phase_seq,
        actor_telegram_id=actor_user_id,
    )
    players = list((await session.scalars(
        select(GamePlayer).where(GamePlayer.game_id == game.id)
    )).all())
    names = {player.user_telegram_id: player.display_name for player in players}
    return [f"{row.number} — {names.get(row.target_telegram_id, 'Игрок')}" for row in rows]


async def record_spy_vote(
    session: AsyncSession,
    *,
    game: GameSession,
    actor_user_id: int,
    number: int,
):
    await ensure_spy_vote_map(session, game=game, actor_user_id=actor_user_id)
    return await record_numbered_action(
        session,
        game_id=game.id,
        expected_phase_seq=game.phase_seq,
        actor_telegram_id=actor_user_id,
        action_type="spy_vote",
        number=number,
    )
