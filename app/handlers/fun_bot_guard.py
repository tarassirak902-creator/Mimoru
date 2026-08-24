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
from app.handlers.fun_commands import (
    ACTION_COOLDOWN_SECONDS,
    FUN_ACTIONS,
    _action_cooldowns,
    _name,
    _pick_text,
)


router = Router(name=__name__)
GROUP_TYPES = {"group", "supergroup"}

BOT_WIN_REPLIES = (
    "😎 {user}, смелая попытка. Но Mimoru даже не пошатнулась и уже записала себе победу. Бота ещё никто не одолел — хоть всей группой собирайтесь.",
    "🤖 {user} решил проверить Mimoru на прочность. Итог: Mimoru победила, как обычно. Хоть толпой приходите — финал всё равно один 😄",
    "⚡ {user} пошёл против Mimoru. Через секунду стало понятно: это была плохая идея. Счёт снова в пользу бота. Победить его пока не удалось никому.",
    "👑 Mimoru посмотрела на {user}, выдержала атаку и спокойно забрала победу. Хотите реванш — собирайте весь чат, но гарантий всё равно нет 😏",
)


class ReplyToMimoru(Filter):
    async def __call__(self, message: Message, bot: Bot) -> bool:
        reply = message.reply_to_message
        return bool(reply and reply.from_user and reply.from_user.id == bot.id)


class ReplyToOtherBot(Filter):
    async def __call__(self, message: Message, bot: Bot) -> bool:
        reply = message.reply_to_message
        return bool(
            reply
            and reply.from_user
            and reply.from_user.is_bot
            and reply.from_user.id != bot.id
        )


def _other_bot_target(message: Message) -> tuple[int, str]:
    reply = message.reply_to_message
    if reply is None or reply.from_user is None:
        return message.chat.id, "участника"

    # Anonymous administrators and messages sent on behalf of a channel/group
    # carry the visible identity in sender_chat. Prefer it over Telegram's
    # technical GroupAnonymousBot identity so game replies look natural.
    if reply.sender_chat is not None:
        return reply.sender_chat.id, reply.sender_chat.title or "анонимного администратора"

    return reply.from_user.id, _name(reply.from_user)


@router.message(
    F.chat.type.in_(GROUP_TYPES),
    F.reply_to_message,
    F.text.casefold().in_(FUN_ACTIONS),
    ReplyToOtherBot(),
)
async def fun_action_against_other_bot(message: Message, session: AsyncSession) -> None:
    if message.from_user is None or message.reply_to_message is None:
        return

    actor = message.from_user
    action = " ".join((message.text or "").casefold().strip().split())

    key = (message.chat.id, actor.id)
    now = time.monotonic()
    previous = _action_cooldowns.get(key, 0.0)
    if now - previous < ACTION_COOLDOWN_SECONDS:
        await message.reply("⏳ Секунду, герой. Дайте чату хотя бы 3 секунды перед следующим игровым действием 😄")
        return
    _action_cooldowns[key] = now

    target_id, target_name = _other_bot_target(message)
    text = _pick_text(action).format(
        user1=_name(actor),
        user2=target_name,
        chance=random.randint(0, 100),
        loot=random.randint(1, 999),
        sentence=random.randint(1, 60),
    )
    await message.reply(text)

    group = await session.scalar(
        select(Group).where(Group.telegram_chat_id == message.chat.id, Group.is_active.is_(True))
    )
    if group is None:
        return
    session.add(
        GameEvent(
            group_id=group.id,
            event_type="action",
            action=action,
            actor_telegram_id=actor.id,
            target_telegram_id=target_id,
            actor_name=_name(actor),
            target_name=target_name,
            outcome="done",
        )
    )
    await session.commit()


@router.message(
    F.chat.type.in_(GROUP_TYPES),
    F.reply_to_message,
    F.text.casefold().in_(FUN_ACTIONS),
    ReplyToMimoru(),
)
async def fun_action_against_bot(message: Message, session: AsyncSession) -> None:
    if message.from_user is None or message.reply_to_message is None or message.reply_to_message.from_user is None:
        return
    actor = message.from_user
    target = message.reply_to_message.from_user
    action = " ".join((message.text or "").casefold().strip().split())
    await message.reply(random.choice(BOT_WIN_REPLIES).format(user=_name(actor)))

    group = await session.scalar(
        select(Group).where(Group.telegram_chat_id == message.chat.id, Group.is_active.is_(True))
    )
    if group is None:
        return
    session.add(
        GameEvent(
            group_id=group.id,
            event_type="bot_attack",
            action=action,
            actor_telegram_id=actor.id,
            target_telegram_id=target.id,
            actor_name=_name(actor),
            target_name="Mimoru",
            outcome="bot_wins",
        )
    )
    await session.commit()
