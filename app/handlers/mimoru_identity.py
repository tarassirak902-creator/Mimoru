from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import BaseFilter
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.fun_models import GameEvent
from app.db.models import DailyStat, Group


router = Router(name=__name__)
GROUP_TYPES = {"group", "supergroup"}
IDENTITY_ALIASES = {"кто ты", "ты кто", "инфа", "информация"}


class ReplyToCurrentBot(BaseFilter):
    async def __call__(self, message: Message, bot: Bot) -> bool:
        replied = message.reply_to_message
        return bool(replied and replied.from_user and replied.from_user.id == bot.id)


async def _mimoru_summary(session: AsyncSession, group: Group, bot_id: int) -> str:
    messages = int(
        await session.scalar(
            select(func.coalesce(func.sum(DailyStat.messages_count), 0)).where(
                DailyStat.group_id == group.id,
                DailyStat.user_telegram_id == bot_id,
            )
        )
        or 0
    )
    actions = int(
        await session.scalar(
            select(func.count(GameEvent.id)).where(
                GameEvent.group_id == group.id,
                GameEvent.event_type == "action",
                GameEvent.actor_telegram_id == bot_id,
            )
        )
        or 0
    )
    rows = (
        await session.execute(
            select(GameEvent.action, func.count(GameEvent.id))
            .where(
                GameEvent.group_id == group.id,
                GameEvent.event_type == "action",
                GameEvent.actor_telegram_id == bot_id,
            )
            .group_by(GameEvent.action)
            .order_by(func.count(GameEvent.id).desc(), GameEvent.action)
            .limit(5)
        )
    ).all()

    lines = [
        "🤖 Я Mimoru — помощник и модератор этой группы.",
        "Слежу за порядком, помогаю администрации и иногда сама вмешиваюсь в развлечения 😄",
        "",
        "📊 Моя активность в этой группе",
        f"💬 Сообщений отправлено: {messages}",
        f"🎭 Игровых действий: {actions}",
    ]
    if rows:
        lines += ["", "🎯 Чаще всего я:"]
        lines.extend(f"• {action} — {count}" for action, count in rows)
    else:
        lines += ["", "🎯 Игровых действий пока не было."]
    return "\n".join(lines)


@router.message(
    F.chat.type.in_(GROUP_TYPES),
    F.text.casefold().in_(IDENTITY_ALIASES),
    ReplyToCurrentBot(),
)
async def mimoru_identity(message: Message, bot: Bot, session: AsyncSession) -> None:
    group = await session.scalar(
        select(Group).where(
            Group.telegram_chat_id == message.chat.id,
            Group.is_active.is_(True),
        )
    )
    if group is None:
        return
    await message.reply(await _mimoru_summary(session, group, bot.id))
