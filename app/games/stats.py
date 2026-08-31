from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GamePlayerGameStats, GamePlayerStats


WIN_RATING_DELTA = 20
LOSS_RATING_DELTA = -10
MIN_RATING = 0


def rating_delta(*, won: bool) -> int:
    return WIN_RATING_DELTA if won else LOSS_RATING_DELTA


async def _group_stats(
    session: AsyncSession,
    *,
    group_id: int,
    user_telegram_id: int,
) -> GamePlayerStats:
    row = await session.scalar(
        select(GamePlayerStats)
        .where(
            GamePlayerStats.group_id == group_id,
            GamePlayerStats.user_telegram_id == user_telegram_id,
        )
        .with_for_update()
    )
    if row is None:
        row = GamePlayerStats(group_id=group_id, user_telegram_id=user_telegram_id)
        session.add(row)
        await session.flush()
    return row


async def _game_stats(
    session: AsyncSession,
    *,
    group_id: int,
    user_telegram_id: int,
    game_type: str,
) -> GamePlayerGameStats:
    row = await session.scalar(
        select(GamePlayerGameStats)
        .where(
            GamePlayerGameStats.group_id == group_id,
            GamePlayerGameStats.user_telegram_id == user_telegram_id,
            GamePlayerGameStats.game_type == game_type,
        )
        .with_for_update()
    )
    if row is None:
        row = GamePlayerGameStats(
            group_id=group_id,
            user_telegram_id=user_telegram_id,
            game_type=game_type,
        )
        session.add(row)
        await session.flush()
    return row


async def apply_game_result(
    session: AsyncSession,
    *,
    group_id: int,
    game_type: str,
    user_telegram_id: int,
    won: bool,
    score_delta: int = 0,
    rating_enabled: bool = True,
    commit: bool = True,
) -> None:
    group_stats = await _group_stats(
        session,
        group_id=group_id,
        user_telegram_id=user_telegram_id,
    )
    game_stats = await _game_stats(
        session,
        group_id=group_id,
        user_telegram_id=user_telegram_id,
        game_type=game_type,
    )

    delta = rating_delta(won=won) if rating_enabled else 0
    for row in (group_stats, game_stats):
        row.games_played += 1
        row.score += score_delta
        row.rating = max(MIN_RATING, row.rating + delta)
        if won:
            row.wins += 1
        else:
            row.losses += 1

    if won:
        group_stats.win_streak += 1
        group_stats.best_win_streak = max(group_stats.best_win_streak, group_stats.win_streak)
    else:
        group_stats.win_streak = 0

    if commit:
        await session.commit()
