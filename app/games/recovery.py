from __future__ import annotations

from datetime import datetime, timezone

import structlog
from aiogram import Bot
from sqlalchemy import select

from app.db.game_models import GameSession
from app.db.models import Group
from app.db.session import SessionFactory
from app.games.enums import GameSessionStatus
from app.games.lobby import close_lobby_message, ensure_lobby_message
from app.games.manager import GameManager
from app.games.panels import ensure_game_panel
from app.games.registry import game_registry


log = structlog.get_logger()
manager = GameManager()


async def _sync_engine_ui(bot: Bot | None, engine, session, game: GameSession) -> None:
    if bot is None:
        return
    sync_ui = getattr(engine, "sync_ui", None)
    if sync_ui is None:
        return
    try:
        await sync_ui(bot, session, game)
    except Exception:
        log.exception("game_ui_sync_failed", game_id=game.id, game_type=game.game_type)


async def recover_active_games(bot: Bot | None = None) -> None:
    async with SessionFactory() as session:
        ids = list((await session.scalars(
            select(GameSession.id).where(
                GameSession.status.in_((
                    GameSessionStatus.LOBBY.value,
                    GameSessionStatus.RUNNING.value,
                    GameSessionStatus.RECOVERING.value,
                ))
            )
        )).all())

    for game_id in ids:
        async with SessionFactory() as session:
            game = await session.scalar(select(GameSession).where(GameSession.id == game_id).with_for_update())
            if game is None or game.status not in {
                GameSessionStatus.LOBBY.value,
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

            if game.status == GameSessionStatus.LOBBY.value:
                if bot is not None:
                    group = await session.get(Group, game.group_id)
                    if group is not None and group.is_active:
                        await ensure_lobby_message(
                            bot,
                            session,
                            group=group,
                            game=game,
                            manager=manager,
                        )
                        await ensure_game_panel(bot, session, group=group, pin=False)
                log.info("game_lobby_recovered", game_id=game.id, game_type=game.game_type)
                continue

            try:
                if game.phase in {"starting", "recovering"}:
                    await entry.engine.start(session, game)
                    log.info(
                        "game_start_recovered",
                        game_id=game.id,
                        game_type=game.game_type,
                    )
                else:
                    await entry.engine.restore(session, game)
            except Exception:
                await session.rollback()
                game = await session.scalar(
                    select(GameSession).where(GameSession.id == game_id).with_for_update()
                )
                if game is not None and game.status in {
                    GameSessionStatus.RUNNING.value,
                    GameSessionStatus.RECOVERING.value,
                }:
                    game.status = GameSessionStatus.RECOVERING.value
                    await session.commit()
                log.exception(
                    "game_recovery_failed",
                    game_id=game_id,
                    game_type=entry.definition.code,
                )
                continue
            if game.status == GameSessionStatus.RECOVERING.value:
                game.status = GameSessionStatus.RUNNING.value
                await session.commit()
            await _sync_engine_ui(bot, entry.engine, session, game)
            log.info("game_recovered", game_id=game.id, game_type=game.game_type, phase=game.phase)


async def process_game_timeouts(bot: Bot | None = None) -> None:
    now = datetime.now(timezone.utc)
    async with SessionFactory() as session:
        ids = list((await session.scalars(
            select(GameSession.id)
            .where(
                GameSession.status.in_((GameSessionStatus.LOBBY.value, GameSessionStatus.RUNNING.value)),
                GameSession.deadline_at.is_not(None),
                GameSession.deadline_at <= now,
            )
            .order_by(GameSession.deadline_at, GameSession.id)
            .limit(100)
        )).all())

    for game_id in ids:
        async with SessionFactory() as session:
            game = await session.scalar(select(GameSession).where(GameSession.id == game_id).with_for_update())
            if (
                game is None
                or game.status not in {GameSessionStatus.LOBBY.value, GameSessionStatus.RUNNING.value}
                or game.deadline_at is None
                or game.deadline_at > datetime.now(timezone.utc)
            ):
                continue
            if game.status == GameSessionStatus.LOBBY.value:
                game.status = GameSessionStatus.CANCELLED.value
                game.phase = "cancelled"
                game.phase_seq += 1
                game.deadline_at = None
                game.finished_at = datetime.now(timezone.utc)
                game.finish_reason = "lobby_timeout"
                await session.commit()
                if bot is not None:
                    group = await session.get(Group, game.group_id)
                    if group is not None:
                        await close_lobby_message(
                            bot,
                            session,
                            group=group,
                            game=game,
                            text="⌛ Лобби закрыто: время ожидания истекло.",
                        )
                        await ensure_game_panel(bot, session, group=group, pin=False)
                log.info("game_lobby_timeout", game_id=game.id, game_type=game.game_type)
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
            game_type = game.game_type
            try:
                await entry.engine.handle_timeout(session, game)
            except Exception:
                await session.rollback()
                game = await session.scalar(
                    select(GameSession).where(GameSession.id == game_id).with_for_update()
                )
                if game is not None and game.status == GameSessionStatus.RUNNING.value:
                    game.status = GameSessionStatus.RECOVERING.value
                    await session.commit()
                log.exception(
                    "game_timeout_failed",
                    game_id=game_id,
                    game_type=game_type,
                    phase_seq=expected_phase_seq,
                )
                continue
            latest = await session.get(GameSession, game.id)
            if latest is not None:
                await _sync_engine_ui(bot, entry.engine, session, latest)
            log.info(
                "game_timeout_processed",
                game_id=game.id,
                game_type=game.game_type,
                phase_seq=expected_phase_seq,
            )