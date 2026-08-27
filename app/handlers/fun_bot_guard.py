from __future__ import annotations

import random
import time

from aiogram import Bot, F, Router
from aiogram.filters import Filter
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.fun_models import GameEvent
from app.db.models import Group
from app.entertainment_contracts import ENTERTAINMENT_ACTIONS, RELATIONSHIP_ACTIONS


router = Router(name=__name__)
GROUP_TYPES = {"group", "supergroup"}
ACTION_COOLDOWN_SECONDS = 3.0
_action_cooldowns: dict[tuple[int, int], float] = {}
ALL_ENTERTAINMENT_ACTIONS = ENTERTAINMENT_ACTIONS | RELATIONSHIP_ACTIONS

BOT_REPLIES = (
    "🤖 {user}, Mimoru тоже получила «{action}». Засчитано 😄",
    "😎 {user} применил к Mimoru «{action}». Бот делает вид, что ничего не произошло.",
    "✨ Mimoru принимает от {user} действие «{action}» и продолжает работать.",
)


class ReplyToMimoru(Filter):
    async def __call__(self, message: Message, bot: Bot) -> bool:
        reply = message.reply_to_message
        return bool(reply and reply.from_user and reply.from_user.id == bot.id)


class ReplyToOtherBot(Filter):
    async def __call__(self, message: Message, bot: Bot) -> bool:
        reply = message.reply_to_message
        return bool(reply and reply.from_user and reply.from_user.is_bot and reply.from_user.id != bot.id)


def _name(user) -> str:
    if user.username:
        return f"@{user.username}"
    return user.full_name or str(user.id)


def _other_bot_target(message: Message) -> tuple[int, str]:
    reply = message.reply_to_message
    if reply is None or reply.from_user is None:
        return message.chat.id, "участника"
    if reply.sender_chat is not None:
        return reply.sender_chat.id, reply.sender_chat.title or "анонимного администратора"
    return reply.from_user.id, _name(reply.from_user)


def _cooldown_ok(message: Message) -> bool:
    if message.from_user is None:
        return False
    key = (message.chat.id, message.from_user.id)
    now = time.monotonic()
    if now - _action_cooldowns.get(key, 0.0) < ACTION_COOLDOWN_SECONDS:
        return False
    _action_cooldowns[key] = now
    return True


@router.message(F.chat.type.in_(GROUP_TYPES), F.reply_to_message, F.text.casefold().in_(ALL_ENTERTAINMENT_ACTIONS), ReplyToOtherBot())
async def entertainment_against_other_bot(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    if not _cooldown_ok(message):
        await message.reply("⏳ Подожди 3 секунды до следующего развлекательного действия 😄")
        return
    action = " ".join((message.text or "").casefold().strip().split())
    target_id, target_name = _other_bot_target(message)
    await message.reply(f"🎭 {_name(message.from_user)} → {target_name}: «{action}».")
    group = await session.scalar(select(Group).where(Group.telegram_chat_id == message.chat.id, Group.is_active.is_(True)))
    if group is not None:
        session.add(GameEvent(group_id=group.id, event_type="entertainment_action", action=action, actor_telegram_id=message.from_user.id, target_telegram_id=target_id, actor_name=_name(message.from_user), target_name=target_name, outcome="done"))
        await session.commit()


@router.message(F.chat.type.in_(GROUP_TYPES), F.reply_to_message, F.text.casefold().in_(ALL_ENTERTAINMENT_ACTIONS), ReplyToMimoru())
async def entertainment_against_mimoru(message: Message, session: AsyncSession) -> None:
    if message.from_user is None or message.reply_to_message is None or message.reply_to_message.from_user is None:
        return
    if not _cooldown_ok(message):
        await message.reply("⏳ Подожди 3 секунды до следующего развлекательного действия 😄")
        return
    actor = message.from_user
    action = " ".join((message.text or "").casefold().strip().split())
    await message.reply(random.choice(BOT_REPLIES).format(user=_name(actor), action=action))
    group = await session.scalar(select(Group).where(Group.telegram_chat_id == message.chat.id, Group.is_active.is_(True)))
    if group is not None:
        session.add(GameEvent(group_id=group.id, event_type="entertainment_action", action=action, actor_telegram_id=actor.id, target_telegram_id=message.reply_to_message.from_user.id, actor_name=_name(actor), target_name="Mimoru", outcome="done"))
        await session.commit()
