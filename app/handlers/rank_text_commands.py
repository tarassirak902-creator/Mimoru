from __future__ import annotations

import re

from aiogram import Bot, F, Router
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group, User
from app.db.rank_models import RankAssignment
from app.middlewares_rank_access import RankAccessModeMiddleware
from app.services.rank_provisioning import remove_assignment
from app.services.user_refs import user_label


router = Router(name=__name__)
router.message.middleware(RankAccessModeMiddleware())
GROUP_TYPES = {"group", "supergroup"}
REMOVE_RE = re.compile(r"^снять(?:\s+(@[A-Za-z0-9_]{3,64}|\d{5,20}))?$", re.IGNORECASE)


async def _group(session: AsyncSession, chat_id: int) -> Group | None:
    return await session.scalar(select(Group).where(
        Group.telegram_chat_id == chat_id,
        Group.is_active.is_(True),
    ))


async def _target_id(session: AsyncSession, message: Message) -> int | None:
    if message.reply_to_message is not None and message.reply_to_message.from_user is not None:
        return message.reply_to_message.from_user.id
    match = REMOVE_RE.match((message.text or "").strip())
    if match is None or not match.group(1):
        return None
    raw = match.group(1)
    if raw.isdigit():
        return int(raw)
    username = raw[1:].casefold()
    return await session.scalar(
        select(User.telegram_id).where(func.lower(User.username) == username).order_by(User.id.desc()).limit(1)
    )


@router.message(F.chat.type.in_(GROUP_TYPES), F.text.regexp(REMOVE_RE))
async def remove_rank_text(message: Message, bot: Bot, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    group = await _group(session, message.chat.id)
    if group is None:
        return
    target_id = await _target_id(session, message)
    if target_id is None:
        await message.reply(
            "Чтобы снять должность, ответьте словом «снять» на сообщение человека или напишите: снять @username / снять Telegram-ID."
        )
        return
    assignment = await session.scalar(select(RankAssignment).where(
        RankAssignment.group_id == group.id,
        RankAssignment.user_telegram_id == target_id,
        RankAssignment.active.is_(True),
    ))
    if assignment is None:
        await message.reply("У этого пользователя нет активной должности Mimoru в этой группе.")
        return

    ok, error = await remove_assignment(bot, session, group, message.from_user.id, assignment)
    if not ok:
        await message.reply(error)
        return
    await message.reply(f"✅ Должность пользователя {await user_label(session, target_id)} снята.")