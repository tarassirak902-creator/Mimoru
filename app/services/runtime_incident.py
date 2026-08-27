from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import structlog
from aiogram import BaseMiddleware, Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import TelegramObject
from redis.asyncio import Redis


RUNTIME_STATE_KEY = "mimoru:runtime:state"
RUNTIME_FATAL_KEY = "mimoru:runtime:last_fatal"
HEARTBEAT_INTERVAL_SECONDS = 10
RUNTIME_STATE_TTL_SECONDS = 7 * 24 * 60 * 60


@dataclass(slots=True)
class RuntimeIncident:
    previous_run_id: str
    started_at: str | None
    last_heartbeat_at: str | None
    processed_updates: int
    reason: str


class RuntimeTracker:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        self.run_id = uuid.uuid4().hex
        self.started_at = datetime.now(timezone.utc)
        self.processed_updates = 0

    async def inspect_previous_run(self) -> RuntimeIncident | None:
        raw = await self.redis.get(RUNTIME_STATE_KEY)
        if not raw:
            return None
        try:
            state = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        if state.get("clean_shutdown") is True:
            return None
        previous_run_id = str(state.get("run_id") or "unknown")
        if previous_run_id == self.run_id:
            return None
        fatal_raw = await self.redis.get(RUNTIME_FATAL_KEY)
        reason = "Причина не была перехвачена процессом (возможен внешний kill/OOM/сбой контейнера)."
        if fatal_raw:
            try:
                fatal = json.loads(fatal_raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                fatal = None
            if isinstance(fatal, dict) and fatal.get("run_id") == previous_run_id:
                reason = str(fatal.get("reason") or reason)
        return RuntimeIncident(
            previous_run_id=previous_run_id,
            started_at=state.get("started_at"),
            last_heartbeat_at=state.get("heartbeat_at"),
            processed_updates=int(state.get("processed_updates") or 0),
            reason=reason,
        )

    async def mark_started(self) -> None:
        await self._write_state(clean_shutdown=False)
        await self.redis.delete(RUNTIME_FATAL_KEY)

    async def _write_state(self, *, clean_shutdown: bool) -> None:
        payload = {
            "run_id": self.run_id,
            "pid": os.getpid(),
            "started_at": self.started_at.isoformat(),
            "heartbeat_at": datetime.now(timezone.utc).isoformat(),
            "processed_updates": self.processed_updates,
            "clean_shutdown": clean_shutdown,
        }
        await self.redis.set(
            RUNTIME_STATE_KEY,
            json.dumps(payload, ensure_ascii=False),
            ex=RUNTIME_STATE_TTL_SECONDS,
        )

    def count_update(self) -> None:
        self.processed_updates += 1

    async def heartbeat_loop(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            await self._write_state(clean_shutdown=False)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=HEARTBEAT_INTERVAL_SECONDS)
            except TimeoutError:
                pass

    async def record_fatal(self, exc: BaseException) -> None:
        reason = f"{type(exc).__name__}: {str(exc)[:1200]}"
        payload = {
            "run_id": self.run_id,
            "at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
        }
        await self.redis.set(
            RUNTIME_FATAL_KEY,
            json.dumps(payload, ensure_ascii=False),
            ex=RUNTIME_STATE_TTL_SECONDS,
        )
        await self._write_state(clean_shutdown=False)

    async def mark_clean_shutdown(self) -> None:
        await self._write_state(clean_shutdown=True)


class RuntimeUpdateCounterMiddleware(BaseMiddleware):
    def __init__(self, tracker: RuntimeTracker) -> None:
        self.tracker = tracker

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        finally:
            self.tracker.count_update()


def _display_time(value: str | None) -> str:
    if not value:
        return "неизвестно"
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().strftime("%d.%m.%Y %H:%M:%S %Z")


def _incident_text(incident: RuntimeIncident, backlog: dict[str, int]) -> str:
    recovered = int(backlog.get("recovered", 0))
    dropped = int(backlog.get("dropped", 0))
    duplicates = int(backlog.get("duplicate_critical_skipped", 0))
    backlog_total = recovered + dropped + duplicates
    restored_at = datetime.now().astimezone().strftime("%d.%m.%Y %H:%M:%S %Z")
    reason = incident.reason.replace("\n", " ").strip()
    return (
        "🚨 Mimoru — аварийный перезапуск\n\n"
        f"› Последний heartbeat: {_display_time(incident.last_heartbeat_at)}\n"
        f"› Бот снова поднялся: {restored_at}\n"
        f"› Причина: {reason}\n"
        f"› Обработано до падения: {incident.processed_updates} update(ов)\n"
        f"› Накопилось во время простоя: {backlog_total}\n"
        f"› Восстановлено критических: {recovered}\n"
        f"› Отброшено устаревших/обычных: {dropped}\n"
        f"› Пропущено дублей: {duplicates}"
    )


async def notify_runtime_incident(
    bot: Bot,
    owner_ids: tuple[int, ...],
    incident: RuntimeIncident | None,
    backlog: dict[str, int],
) -> None:
    if incident is None or not owner_ids:
        return
    log = structlog.get_logger()
    text = _incident_text(incident, backlog)
    for owner_id in owner_ids:
        try:
            await bot.send_message(owner_id, text)
        except (TelegramForbiddenError, TelegramBadRequest):
            log.warning("runtime_incident_notice_rejected", owner_id=owner_id)
        except Exception:
            log.exception("runtime_incident_notice_failed", owner_id=owner_id)
