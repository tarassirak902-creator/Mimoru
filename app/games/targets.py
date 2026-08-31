from __future__ import annotations

import random
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GameTargetMap
from app.games.locks import advisory_xact_lock


_TARGET_MAP_LOCK_NAMESPACE = 4_676_946


class TargetMapError(RuntimeError):
    pass


async def get_target_map(
    session: AsyncSession,
    *,
    game_id: int,
    phase_seq: int,
    actor_telegram_id: int,
) -> list[GameTargetMap]:
    rows = await session.scalars(
        select(GameTargetMap)
        .where(
            GameTargetMap.game_id == game_id,
            GameTargetMap.phase_seq == phase_seq,
            GameTargetMap.actor_telegram_id == actor_telegram_id,
        )
        .order_by(GameTargetMap.number)
    )
    return list(rows.all())


async def ensure_target_map(
    session: AsyncSession,
    *,
    game_id: int,
    phase_seq: int,
    actor_telegram_id: int,
    target_telegram_ids: Sequence[int],
) -> list[GameTargetMap]:
    targets = list(dict.fromkeys(int(value) for value in target_telegram_ids))
    if not targets:
        return []

    await advisory_xact_lock(
        session,
        namespace=_TARGET_MAP_LOCK_NAMESPACE,
        key=game_id,
    )
    existing = await get_target_map(
        session,
        game_id=game_id,
        phase_seq=phase_seq,
        actor_telegram_id=actor_telegram_id,
    )
    if existing:
        existing_targets = {row.target_telegram_id for row in existing}
        if existing_targets != set(targets):
            await session.rollback()
            raise TargetMapError("target set changed inside active phase")
        await session.commit()
        return existing

    shuffled = targets[:]
    random.SystemRandom().shuffle(shuffled)
    rows = [
        GameTargetMap(
            game_id=game_id,
            phase_seq=phase_seq,
            actor_telegram_id=actor_telegram_id,
            number=number,
            target_telegram_id=target_id,
        )
        for number, target_id in enumerate(shuffled, start=1)
    ]
    session.add_all(rows)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    return await get_target_map(
        session,
        game_id=game_id,
        phase_seq=phase_seq,
        actor_telegram_id=actor_telegram_id,
    )


async def resolve_target_number(
    session: AsyncSession,
    *,
    game_id: int,
    phase_seq: int,
    actor_telegram_id: int,
    number: int,
) -> int | None:
    return await session.scalar(
        select(GameTargetMap.target_telegram_id).where(
            GameTargetMap.game_id == game_id,
            GameTargetMap.phase_seq == phase_seq,
            GameTargetMap.actor_telegram_id == actor_telegram_id,
            GameTargetMap.number == number,
        )
    )


async def clear_target_maps_before_phase(
    session: AsyncSession,
    *,
    game_id: int,
    phase_seq: int,
) -> int:
    result = await session.execute(
        delete(GameTargetMap).where(
            GameTargetMap.game_id == game_id,
            GameTargetMap.phase_seq < phase_seq,
        )
    )
    await session.commit()
    return int(result.rowcount or 0)
