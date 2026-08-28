from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from app.db.game_models import GameSession
from app.db.session import SessionFactory
from app.games.enums import GameSessionStatus
from app.games.registry import game_registry


log = structlog.get_logger()


async def recover_active_games() -> None:
    async with SessionFactory() as session:
        ids = list(
            (
                await session.scalars(
                    select(GameSession.id).where(
                        GameSession.status.in_(
                            (
                                GameSessionStatus.RUNNING.value,
                                GameSessionStatus.RECOVERING.value,
                            )
                        )
                    )
                )
            ).all()
        )

    for game_id in ids:
        async with SessionFactory() as session:
            game = await session.scalar(
                select(GameSession)
                .where(GameSession.id == game_id)
                .with_for_update()
            )
            if game is None or game.status not in {
                GameSessionStatus.RUNNING.value,
                GameSessionStatus.RECOVERING.value,
            }:
                continue
            entry = game_registry.get_entry(game.game_type)
            if entry is None:
                game.status = GameSessionStatus.CANCELLED.value
                game.finished_at = datetime.now(timezone.utc)
                game.finish_reason = "missing_game_engine"
                await session.commit()
                log.error("game_recovery_engine_missing", game_id=game.id, game_type=game.game_type)
                continue
            try:
                await entry.engine.restore(session, game)
            except Exception:
                game.status = GameSessionStatus.RECOVERING.value
                await session.commit()
                log.exception("game_recovery_failed", game_id=game.id, game_type=game.game_type)
                continue
            if game.status == GameSessionStatus.RECOVERING.value:
                game.status = GameSessionStatus.RUNNING.value
                await session.commit()
            log.info("game_recovered", game_id=game.id, game_type=game.game_type, phase=game.phase)


async def process_game_timeouts() -> None:
    now = datetime.now(timezone.utc)
    async with SessionFactory() as session:
        ids = list(
            (
                await session.scalars(
                    select(GameSession.id)
                    .where(
                        GameSession.status == GameSessionStatus.RUNNING.value,
                        GameSession.deadline_at.is_not(None),
                        GameSession.deadline_at <= now,
                    )
                    .order_by(GameSession.deadline_at, GameSession.id)
                    .limit(100)
                )
            ).all()
        )

    for game_id in ids:
        async with SessionFactory() as session:
            game = await session.scalar(
                select(GameSession)
                .where(GameSession.id == game_id)
                .with_for_update()
            )
            if (
                game is None
                or game.status != GameSessionStatus.RUNNING.value
                or game.deadline_at is None
                or game.deadline_at > datetime.now(timezone.utc)
            ):
                continue
            entry = game_registry.get_entry(game.game_type)
            if entry is None:
                game.status = GameSessionStatus.CANCELLED.value
                game.finished_at = datetime.now(timezone.utc)
                game.finish_reason = "missing_game_engine"
                await session.commit()
                log.error("game_timeout_engine_missing", game_id=game.id, game_type=game.game_type)
                continue
            expected_phase_seq = game.phase_seq
            try:
                await entry.engine.handle_timeout(session, game)
            except Exception:
                game.status = GameSessionStatus.RECOVERING.value
                await session.commit()
                log.exception(
                    "game_timeout_failed",
                    game_id=game.id,
                    game_type=game.game_type,
                    phase_seq=expected_phase_seq,
                )
                continue
            log.info(
                "game_timeout_processed",
                game_id=game.id,
                game_type=game.game_type,
                phase_seq=expected_phase_seq,
            )
