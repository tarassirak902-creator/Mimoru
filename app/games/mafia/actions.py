from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GameAction, GamePlayer, GameSession
from app.games.actions import GameActionError, record_numbered_action
from app.games.mafia.game import MafiaPhase
from app.games.targets import ensure_target_map, get_target_map


ROLE_ACTIONS = {
    "mafia": "mafia_kill",
    "doctor": "doctor_heal",
    "commissioner": "commissioner_check",
}


async def _actor(session: AsyncSession, game_id: int, user_id: int) -> GamePlayer | None:
    return await session.scalar(
        select(GamePlayer).where(
            GamePlayer.game_id == game_id,
            GamePlayer.user_telegram_id == user_id,
        )
    )


async def available_target_ids(
    session: AsyncSession,
    *,
    game: GameSession,
    actor: GamePlayer,
) -> list[int]:
    alive = list((await session.scalars(
        select(GamePlayer)
        .where(GamePlayer.game_id == game.id, GamePlayer.status == "alive")
        .order_by(GamePlayer.id)
    )).all())
    if game.phase == MafiaPhase.DAY_VOTING.value:
        return [player.user_telegram_id for player in alive if player.user_telegram_id != actor.user_telegram_id]
    if game.phase != MafiaPhase.NIGHT_ACTIONS.value:
        return []
    if actor.role == "mafia":
        return [player.user_telegram_id for player in alive if player.team != "mafia"]
    if actor.role == "doctor":
        state = dict(game.state_json or {})
        last_healed = state.get("last_healed_user_id")
        result = [player.user_telegram_id for player in alive]
        if not state.get("doctor_can_self_heal", True):
            result = [uid for uid in result if uid != actor.user_telegram_id]
        if not state.get("doctor_can_heal_same_player_twice", False) and last_healed is not None:
            result = [uid for uid in result if uid != int(last_healed)]
        return result
    if actor.role == "commissioner":
        return [player.user_telegram_id for player in alive if player.user_telegram_id != actor.user_telegram_id]
    return []


async def ensure_actor_targets(
    session: AsyncSession,
    *,
    game: GameSession,
    actor_user_id: int,
) -> list[tuple[int, int]]:
    actor = await _actor(session, game.id, actor_user_id)
    if actor is None or actor.status != "alive":
        raise GameActionError("actor is not alive")
    targets = await available_target_ids(session, game=game, actor=actor)
    rows = await ensure_target_map(
        session,
        game_id=game.id,
        phase_seq=game.phase_seq,
        actor_telegram_id=actor_user_id,
        target_telegram_ids=targets,
    )
    return [(row.number, row.target_telegram_id) for row in rows]


async def target_map_lines(
    session: AsyncSession,
    *,
    game: GameSession,
    actor_user_id: int,
    start: int = 1,
    end: int = 7,
) -> list[str]:
    await ensure_actor_targets(session, game=game, actor_user_id=actor_user_id)
    rows = await get_target_map(
        session,
        game_id=game.id,
        phase_seq=game.phase_seq,
        actor_telegram_id=actor_user_id,
    )
    ids = [row.target_telegram_id for row in rows if start <= row.number <= end]
    players = list((await session.scalars(
        select(GamePlayer).where(GamePlayer.game_id == game.id, GamePlayer.user_telegram_id.in_(ids))
    )).all()) if ids else []
    names = {player.user_telegram_id: player.display_name for player in players}
    return [
        f"{row.number} — {names.get(row.target_telegram_id, 'Игрок')}"
        for row in rows
        if start <= row.number <= end
    ]


async def record_mafia_number_action(
    session: AsyncSession,
    *,
    game: GameSession,
    actor_user_id: int,
    number: int,
) -> tuple[GameAction, bool]:
    actor = await _actor(session, game.id, actor_user_id)
    if actor is None or actor.status != "alive":
        raise GameActionError("actor is not alive")
    if game.phase == MafiaPhase.DAY_VOTING.value:
        action_type = "day_vote"
    elif game.phase == MafiaPhase.NIGHT_ACTIONS.value:
        action_type = ROLE_ACTIONS.get(actor.role or "")
        if action_type is None:
            raise GameActionError("role has no night action")
    else:
        raise GameActionError("phase does not accept target actions")
    await ensure_actor_targets(session, game=game, actor_user_id=actor_user_id)
    return await record_numbered_action(
        session,
        game_id=game.id,
        expected_phase_seq=game.phase_seq,
        actor_telegram_id=actor_user_id,
        action_type=action_type,
        number=number,
    )
