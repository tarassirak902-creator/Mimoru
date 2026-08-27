from __future__ import annotations

from datetime import datetime, timezone

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GameMessage


log = structlog.get_logger()


async def register_game_message(
    session: AsyncSession,
    *,
    game_id: int,
    chat_id: int,
    message_id: int,
    kind: str = "temporary",
) -> GameMessage:
    record = await session.scalar(
        select(GameMessage).where(
            GameMessage.game_id == game_id,
            GameMessage.message_id == message_id,
        )
    )
    if record is None:
        record = GameMessage(
            game_id=game_id,
            chat_id=chat_id,
            message_id=message_id,
            kind=kind,
            active=True,
        )
        session.add(record)
    else:
        record.chat_id = chat_id
        record.kind = kind
        record.active = True
        record.retired_at = None
    await session.commit()
    await session.refresh(record)
    return record


async def retire_game_message(
    bot: Bot,
    session: AsyncSession,
    *,
    record: GameMessage,
    replacement_text: str | None = None,
) -> None:
    if not record.active:
        return
    try:
        if replacement_text is not None:
            await bot.edit_message_text(
                chat_id=record.chat_id,
                message_id=record.message_id,
                text=replacement_text,
                reply_markup=None,
            )
        else:
            await bot.delete_message(record.chat_id, record.message_id)
    except TelegramBadRequest as error:
        text = str(error).casefold()
        if not any(
            marker in text
            for marker in (
                "message to delete not found",
                "message can't be deleted",
                "message is not modified",
                "message to edit not found",
            )
        ):
            log.info(
                "game_message_retire_failed",
                game_id=record.game_id,
                message_id=record.message_id,
                error=str(error),
            )
    except TelegramForbiddenError as error:
        log.info(
            "game_message_retire_forbidden",
            game_id=record.game_id,
            message_id=record.message_id,
            error=str(error),
        )
    record.active = False
    record.retired_at = datetime.now(timezone.utc)
    await session.commit()


async def retire_active_messages(
    bot: Bot,
    session: AsyncSession,
    *,
    game_id: int,
    kind: str | None = None,
    replacement_text: str | None = None,
) -> int:
    query = select(GameMessage).where(
        GameMessage.game_id == game_id,
        GameMessage.active.is_(True),
    )
    if kind is not None:
        query = query.where(GameMessage.kind == kind)
    records = list((await session.scalars(query.order_by(GameMessage.id))).all())
    for record in records:
        await retire_game_message(
            bot,
            session,
            record=record,
            replacement_text=replacement_text,
        )
    return len(records)


async def upsert_phase_message(
    bot: Bot,
    session: AsyncSession,
    *,
    game_id: int,
    chat_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    kind: str = "phase",
) -> Message | None:
    existing = await session.scalar(
        select(GameMessage)
        .where(
            GameMessage.game_id == game_id,
            GameMessage.kind == kind,
            GameMessage.active.is_(True),
        )
        .order_by(GameMessage.id.desc())
        .limit(1)
    )
    if existing is not None:
        try:
            await bot.edit_message_text(
                chat_id=existing.chat_id,
                message_id=existing.message_id,
                text=text,
                reply_markup=reply_markup,
            )
            return None
        except TelegramBadRequest as error:
            if "message is not modified" in str(error).casefold():
                return None
            existing.active = False
            existing.retired_at = datetime.now(timezone.utc)
            await session.commit()
        except TelegramForbiddenError as error:
            log.info(
                "game_phase_message_edit_forbidden",
                game_id=game_id,
                message_id=existing.message_id,
                error=str(error),
            )
            return None

    try:
        message = await bot.send_message(chat_id, text, reply_markup=reply_markup)
    except (TelegramBadRequest, TelegramForbiddenError) as error:
        log.warning("game_phase_message_send_failed", game_id=game_id, error=str(error))
        return None
    await register_game_message(
        session,
        game_id=game_id,
        chat_id=chat_id,
        message_id=message.message_id,
        kind=kind,
    )
    return message
