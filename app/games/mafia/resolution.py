from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GameAction, GamePlayer, GameResult, GameSession
from app.games.enums import GameSessionStatus
from app.games.stats import apply_game_result


async def alive_players(session: AsyncSession, game_id: int, *, for_update: bool = False) -> list[GamePlayer]:
    query = (
        select(GamePlayer)
        .where(GamePlayer.game_id == game_id, GamePlayer.status == "alive")
        .order_by(GamePlayer.id)
    )
    if for_update:
        query = query.with_for_update()
    return list((await session.scalars(query)).all())


def plurality_target(actions: list[GameAction]) -> int | None:
    targets = [action.target_telegram_id for action in actions if action.target_telegram_id is not None]
    if not targets:
        return None
    counts = Counter(targets)
    highest = max(counts.values())
    winners = [target for target, count in counts.items() if count == highest]
    return winners[0] if len(winners) == 1 else None


async def resolve_day_vote(session: AsyncSession, game: GameSession) -> dict:
    actions = list((await session.scalars(
        select(GameAction).where(
            GameAction.game_id == game.id,
            GameAction.phase_seq == game.phase_seq,
            GameAction.action_type == "day_vote",
        )
    )).all())
    target_id = plurality_target(actions)
    result = {"executed_user_id": None, "tie": target_id is None, "votes": len(actions)}
    if target_id is not None:
        target = await session.scalar(
            select(GamePlayer)
            .where(GamePlayer.game_id == game.id, GamePlayer.user_telegram_id == target_id)
            .with_for_update()
        )
        if target is not None and target.status == "alive":
            target.status = "dead"
            result["executed_user_id"] = target.user_telegram_id
            result["executed_name"] = target.display_name
            result["executed_role"] = target.role
    state = dict(game.state_json or {})
    state["last_day_result"] = result
    game.state_json = state
    await session.commit()
    return result


async def resolve_night(session: AsyncSession, game: GameSession) -> dict:
    actions = list((await session.scalars(
        select(GameAction).where(
            GameAction.game_id == game.id,
            GameAction.phase_seq == game.phase_seq,
        )
    )).all())
    mafia_actions = [action for action in actions if action.action_type == "mafia_kill"]
    doctor_action = next((action for action in actions if action.action_type == "doctor_heal"), None)
    kill_id = plurality_target(mafia_actions)
    heal_id = doctor_action.target_telegram_id if doctor_action is not None else None
    victim_id = None if kill_id is not None and kill_id == heal_id else kill_id
    result = {
        "attacked_user_id": kill_id,
        "healed_user_id": heal_id,
        "killed_user_id": victim_id,
        "saved": kill_id is not None and kill_id == heal_id,
    }
    if victim_id is not None:
        victim = await session.scalar(
            select(GamePlayer)
            .where(GamePlayer.game_id == game.id, GamePlayer.user_telegram_id == victim_id)
            .with_for_update()
        )
        if victim is not None and victim.status == "alive":
            victim.status = "dead"
            result["killed_name"] = victim.display_name
            result["killed_role"] = victim.role
    if doctor_action is not None:
        state = dict(game.state_json or {})
        state["last_healed_user_id"] = heal_id
        state["last_night_result"] = result
        game.state_json = state
    else:
        state = dict(game.state_json or {})
        state["last_night_result"] = result
        game.state_json = state
    await session.commit()
    return result


async def winner(session: AsyncSession, game_id: int) -> str | None:
    alive = await alive_players(session, game_id)
    mafia = sum(1 for player in alive if player.team == "mafia")
    town = sum(1 for player in alive if player.team != "mafia")
    if mafia == 0:
        return "town"
    if mafia >= town:
        return "mafia"
    return None


async def finish_game(session: AsyncSession, game: GameSession, winning_team: str) -> None:
    game = await session.scalar(select(GameSession).where(GameSession.id == game.id).with_for_update())
    if game is None or game.status == GameSessionStatus.FINISHED.value:
        return
    players = list((await session.scalars(
        select(GamePlayer).where(GamePlayer.game_id == game.id).order_by(GamePlayer.id).with_for_update()
    )).all())
    now = datetime.now(timezone.utc)
    game.status = GameSessionStatus.FINISHED.value
    game.phase = "finished"
    game.phase_seq += 1
    game.deadline_at = None
    game.finished_at = now
    game.finish_reason = f"winner:{winning_team}"
    duration = int((now - game.started_at).total_seconds()) if game.started_at else None
    existing_result = await session.scalar(select(GameResult).where(GameResult.game_id == game.id))
    if existing_result is None:
        session.add(GameResult(
            game_id=game.id,
            group_id=game.group_id,
            game_type=game.game_type,
            winner_type="team",
            winner_json={"team": winning_team},
            summary_json={"rounds": game.round_no, "players": len(players)},
            duration_seconds=duration,
        ))
    await session.commit()
    for player in players:
        await apply_game_result(
            session,
            group_id=game.group_id,
            game_type=game.game_type,
            user_telegram_id=player.user_telegram_id,
            won=player.team == winning_team,
            rating_enabled=True,
        )
