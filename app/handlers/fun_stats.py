from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.fun_models import GameEvent, GroupMarriage
from app.db.models import Group
from app.services.access import is_service_owner, is_telegram_admin


router = Router(name=__name__)
GROUP_TYPES = {"group", "supergroup"}


@router.message(F.chat.type.in_(GROUP_TYPES), F.text.casefold() == "стата игр")
async def game_statistics(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    group = await session.scalar(
        select(Group).where(Group.telegram_chat_id == message.chat.id, Group.is_active.is_(True))
    )
    if group is None:
        return

    user_id = message.from_user.id
    allowed = (
        user_id == group.owner_telegram_id
        or is_service_owner(user_id)
        or await is_telegram_admin(message.bot, message.chat.id, user_id)
    )
    if not allowed:
        await message.reply("📊 Статистика игр доступна только администрации этой группы.")
        return

    action_rows = (await session.execute(
        select(GameEvent.action, func.count(GameEvent.id)).where(
            GameEvent.group_id == group.id,
            GameEvent.event_type == "action",
            GameEvent.outcome != "bot_wins",
        ).group_by(GameEvent.action).order_by(func.count(GameEvent.id).desc(), GameEvent.action)
    )).all()
    action_counts = {str(action): int(count) for action, count in action_rows}

    proposal_rows = (await session.execute(
        select(GameEvent.action, func.count(GameEvent.id)).where(
            GameEvent.group_id == group.id,
            GameEvent.event_type == "proposal",
            GameEvent.outcome == "accepted",
        ).group_by(GameEvent.action)
    )).all()
    proposal_counts = {str(action): int(count) for action, count in proposal_rows}

    active_marriages = int(await session.scalar(
        select(func.count(GroupMarriage.id)).where(
            GroupMarriage.group_id == group.id,
            GroupMarriage.active.is_(True),
        )
    ) or 0)

    bot_attacks = int(await session.scalar(
        select(func.count(GameEvent.id)).where(
            GameEvent.group_id == group.id,
            or_(
                GameEvent.event_type == "bot_attack",
                GameEvent.outcome == "bot_wins",
            ),
        )
    ) or 0)

    kicks = action_counts.get("пнуть", 0) + action_counts.get("пнуть под зад", 0)
    bites = action_counts.get("укусить", 0) + action_counts.get("покусать", 0)
    kisses = action_counts.get("поцеловать", 0) + action_counts.get("засосать", 0)
    total_actions = sum(action_counts.values())

    summary = (
        "🎮 Статистика игр группы\n\n"
        f"💍 Активных браков: {active_marriages}\n"
        f"🥊 Драк: {proposal_counts.get('fight', 0)}\n"
        f"⚔️ Дуэлей: {proposal_counts.get('duel', 0)}\n"
        f"🌹 Свиданий: {proposal_counts.get('date', 0)}\n"
        f"❤️ Признаний: {proposal_counts.get('love', 0)}\n"
        f"💢 Ссор: {action_counts.get('поссориться', 0)}\n"
        f"🤝 Примирений: {action_counts.get('помириться', 0)}\n"
        f"🤖 Нападений на Mimoru: {bot_attacks}\n\n"
        "Популярные действия:\n"
        f"👊 Ударов: {action_counts.get('ударить', 0)}\n"
        f"🦷 Укусов: {bites}\n"
        f"🦵 Пинков: {kicks}\n"
        f"💋 Поцелуйчиков: {kisses}\n\n"
        f"Всего обычных игровых действий: {total_actions}"
    )

    if action_rows:
        details = "\n".join(f"• {action} — {count}" for action, count in action_rows)
        summary += f"\n\nВсе использованные действия:\n{details}"
    else:
        summary += "\n\nСтатистика обычных действий пока пустая."

    await message.reply(summary)
