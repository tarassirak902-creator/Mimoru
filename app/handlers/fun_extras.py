from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.fun_models import FunGroupSettings, GameEvent, GroupMarriage
from app.db.models import Group
from app.services.access import is_service_owner


router = Router(name=__name__)
GROUP_TYPES = {"group", "supergroup"}


async def _group(
    session: AsyncSession,
    chat_id: int,
    *,
    for_update: bool = False,
) -> Group | None:
    query = select(Group).where(
        Group.telegram_chat_id == chat_id,
        Group.is_active.is_(True),
    )
    if for_update:
        query = query.with_for_update()
    return await session.scalar(query)


def _leader(rows) -> str:
    if not rows:
        return "пока нет"
    _uid, name, count = rows[0]
    return f"{name} — {count}"


async def _top_for_actions(session: AsyncSession, group_id: int, actions: tuple[str, ...], *, bot_attacks: bool = False):
    conditions = [GameEvent.group_id == group_id, GameEvent.actor_name != "Mimoru"]
    if bot_attacks:
        conditions.append(or_(GameEvent.event_type == "bot_attack", GameEvent.outcome == "bot_wins"))
    else:
        conditions.extend((GameEvent.event_type == "action", GameEvent.action.in_(actions)))
    return (await session.execute(
        select(GameEvent.actor_telegram_id, func.max(GameEvent.actor_name), func.count(GameEvent.id))
        .where(*conditions)
        .group_by(GameEvent.actor_telegram_id)
        .order_by(func.count(GameEvent.id).desc())
        .limit(10)
    )).all()


@router.message(F.chat.type.in_(GROUP_TYPES), F.text.casefold().in_({"моя стата игр", "моя игровая стата"}))
async def my_game_stats(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    group = await _group(session, message.chat.id)
    if group is None:
        return
    uid = message.from_user.id
    action_rows = (await session.execute(
        select(GameEvent.action, func.count(GameEvent.id)).where(
            GameEvent.group_id == group.id,
            GameEvent.event_type == "action",
            GameEvent.actor_telegram_id == uid,
        ).group_by(GameEvent.action).order_by(func.count(GameEvent.id).desc()).limit(8)
    )).all()
    made = sum(int(count) for _, count in action_rows)
    received = int(await session.scalar(select(func.count(GameEvent.id)).where(
        GameEvent.group_id == group.id,
        GameEvent.event_type == "action",
        GameEvent.target_telegram_id == uid,
        GameEvent.outcome != "bot_wins",
    )) or 0)
    bot_attacks = int(await session.scalar(select(func.count(GameEvent.id)).where(
        GameEvent.group_id == group.id,
        GameEvent.actor_telegram_id == uid,
        or_(GameEvent.event_type == "bot_attack", GameEvent.outcome == "bot_wins"),
    )) or 0)
    proposals = int(await session.scalar(select(func.count(GameEvent.id)).where(
        GameEvent.group_id == group.id,
        GameEvent.event_type == "proposal",
        GameEvent.actor_telegram_id == uid,
        GameEvent.outcome == "accepted",
    )) or 0)
    marriages = int(await session.scalar(select(func.count(GroupMarriage.id)).where(
        GroupMarriage.group_id == group.id,
        or_(GroupMarriage.user1_telegram_id == uid, GroupMarriage.user2_telegram_id == uid),
    )) or 0)
    active_marriage = bool(await session.scalar(select(GroupMarriage.id).where(
        GroupMarriage.group_id == group.id,
        GroupMarriage.active.is_(True),
        or_(GroupMarriage.user1_telegram_id == uid, GroupMarriage.user2_telegram_id == uid),
    ).limit(1)))
    text = (
        "🎮 Ваша игровая статистика\n\n"
        f"🎭 Действий совершено: {made}\n"
        f"🎯 Действий получено: {received}\n"
        f"💌 Принятых предложений: {proposals}\n"
        f"💍 Браков за всё время: {marriages}\n"
        f"❤️ Сейчас в браке: {'да' if active_marriage else 'нет'}\n"
        f"🤖 Нападений на Mimoru: {bot_attacks}"
    )
    if action_rows:
        text += "\n\nВаши любимые действия:\n" + "\n".join(f"• {action} — {count}" for action, count in action_rows)
    text += "\n\nСтатистика относится только к этой группе."
    await message.reply(text)


@router.message(F.chat.type.in_(GROUP_TYPES), F.text.casefold().in_({"топ игр", "топ игроков"}))
async def game_top(message: Message, session: AsyncSession) -> None:
    group = await _group(session, message.chat.id)
    if group is None:
        return
    overall = (await session.execute(
        select(GameEvent.actor_telegram_id, func.max(GameEvent.actor_name), func.count(GameEvent.id))
        .where(
            GameEvent.group_id == group.id,
            GameEvent.event_type.in_(("action", "proposal", "bot_attack")),
            GameEvent.actor_name != "Mimoru",
        ).group_by(GameEvent.actor_telegram_id).order_by(func.count(GameEvent.id).desc()).limit(10)
    )).all()
    if not overall:
        await message.reply("🏆 Топ игр пока пуст. Поиграйте немного — и здесь появятся лидеры группы.")
        return
    fighters = await _top_for_actions(session, group.id, ("ударить", "пнуть", "пнуть под зад", "дать леща", "укусить", "покусать", "подраться"))
    romantics = await _top_for_actions(session, group.id, ("обнять", "поцеловать", "засосать", "подкатить", "сделать комплимент", "украсть сердце"))
    bot_attackers = await _top_for_actions(session, group.id, (), bot_attacks=True)
    lines = [f"{index}. {name} — {count}" for index, (_, name, count) in enumerate(overall, start=1)]
    await message.reply(
        "🏆 Топ игр группы\n\n"
        f"🎮 Самый активный: {_leader(overall)}\n"
        f"🥊 Самый драчливый: {_leader(fighters)}\n"
        f"❤️ Самый романтичный: {_leader(romantics)}\n"
        f"🤖 Чаще всех нападал на Mimoru: {_leader(bot_attackers)}\n\n"
        "Общий рейтинг:\n" + "\n".join(lines)
    )


async def _owner_allowed(group: Group, user_id: int) -> bool:
    return user_id == group.owner_telegram_id or is_service_owner(user_id)


@router.message(F.chat.type.in_(GROUP_TYPES), F.text.casefold().in_({"настройки игр", "авто игры"}))
async def game_settings(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    group = await _group(session, message.chat.id)
    if group is None:
        return
    if not await _owner_allowed(group, message.from_user.id):
        await message.reply("⚙️ Настройки автоматических игр может менять только владелец группы.")
        return
    settings = await session.scalar(select(FunGroupSettings).where(FunGroupSettings.group_id == group.id))
    if settings is None:
        settings = FunGroupSettings(group_id=group.id)
        session.add(settings)
        await session.commit()
    labels = {"15_20": "15–20 минут", "30_40": "30–40 минут", "60": "60 минут"}
    await message.reply(
        "⚙️ Автоматические игры Mimoru\n\n"
        f"Состояние: {'включены' if settings.auto_enabled else 'выключены'}\n"
        f"Интервал: {labels.get(settings.interval_code, '15–20 минут')}\n\n"
        "Mimoru выбирает только тех участников, которые были активны за последнее игровое окно и не включили /imunitet.\n\n"
        "Чтобы изменить настройку, напишите:\n"
        "авто игры вкл\n"
        "авто игры выкл\n"
        "авто игры 15-20\n"
        "авто игры 30-40\n"
        "авто игры 60"
    )


@router.message(F.chat.type.in_(GROUP_TYPES), F.text.casefold().regexp(r"^авто игры (вкл|выкл|15-20|30-40|60)$"))
async def change_game_settings(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    group = await _group(session, message.chat.id, for_update=True)
    if group is None:
        return
    if not await _owner_allowed(group, message.from_user.id):
        await message.reply("⚙️ Изменять автоматические игры может только владелец группы.")
        return
    settings = await session.scalar(select(FunGroupSettings).where(FunGroupSettings.group_id == group.id))
    if settings is None:
        settings = FunGroupSettings(group_id=group.id)
        session.add(settings)
    value = (message.text or "").casefold().rsplit(" ", 1)[1]
    if value == "вкл":
        settings.auto_enabled = True
        answer = "🎮 Автоматические игры Mimoru включены."
    elif value == "выкл":
        settings.auto_enabled = False
        answer = "🛑 Автоматические игры Mimoru выключены. Обычные развлечения участников продолжат работать."
    else:
        settings.interval_code = {"15-20": "15_20", "30-40": "30_40", "60": "60"}[value]
        answer = f"⏱ Интервал автоматических игр изменён на {value.replace('-', '–')} минут."
    await session.commit()
    await message.reply(answer)
