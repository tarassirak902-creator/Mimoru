from __future__ import annotations

import math
import random
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.fun_models import GameEvent, GroupMarriage
from app.db.models import Group
from app.services.access import is_service_owner, is_telegram_admin


router = Router(name=__name__)
GROUP_TYPES = {"group", "supergroup"}
FOREIGN_BUTTON_NOTICE = "Не для тебя мать кнопки прислала, отдыхай! Выпей лучше валерьянки и узбогойся..."
HISTORY_PAGE_SIZE = 8

PROPOSALS = {
    "пожениться": ("marry", "💍 {user1} сделал предложение {user2}. Что ответит {user2}?"),
    "позвать на свидание": ("date", "🌹 {user1} позвал {user2} на свидание. Ответ за {user2}."),
    "признаться в любви": ("love", "❤️ {user1} признался в любви {user2}. Кажется, весь чат замолчал в ожидании ответа."),
    "предложить любовь": ("romance", "😏 {user1} предложил {user2} романтический вечер. Решение принимает только {user2}."),
    "дуэль": ("duel", "⚔️ {user1} вызвал {user2} на дуэль. {user2}, принимаешь вызов?"),
    "драка": ("fight", "🥊 {user1} вызвал {user2} на эпическую драку. {user2}, принимаешь?"),
    "подраться": ("fight", "🥊 {user1} вызвал {user2} на эпическую драку. {user2}, принимаешь?"),
}
PROPOSAL_ACTIONS = frozenset(PROPOSALS)

KIND_LABEL = {
    "marry": "предложение руки и сердца",
    "date": "свидание",
    "love": "признание",
    "romance": "романтическое предложение",
    "duel": "дуэль",
    "fight": "драку",
}

HISTORY_COMMANDS = {
    "браки": "marry",
    "драки": "fight",
    "дуэли": "duel",
    "свидания": "date",
    "признания": "love",
    "романтика": "romance",
    "романтические предложения": "romance",
}
HISTORY_WORDS = frozenset(HISTORY_COMMANDS)
HISTORY_TITLES = {
    "marry": "💍 Браки группы",
    "fight": "🥊 Драки группы",
    "duel": "⚔️ Дуэли группы",
    "date": "🌹 Свидания группы",
    "love": "❤️ Признания в любви",
    "romance": "😏 Романтические предложения",
}


def _name(user) -> str:
    if user.username:
        return f"@{user.username}"
    return user.full_name or str(user.id)


async def _active_group(session: AsyncSession, chat_id: int) -> Group | None:
    return await session.scalar(
        select(Group).where(Group.telegram_chat_id == chat_id, Group.is_active.is_(True))
    )


async def _active_marriage(session: AsyncSession, group_id: int, user_id: int) -> GroupMarriage | None:
    return await session.scalar(
        select(GroupMarriage).where(
            GroupMarriage.group_id == group_id,
            GroupMarriage.active.is_(True),
            or_(
                GroupMarriage.user1_telegram_id == user_id,
                GroupMarriage.user2_telegram_id == user_id,
            ),
        )
    )


def _proposal_markup(kind: str, group_id: int, actor_id: int, target_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Принять",
                callback_data=f"fs:{kind}:{group_id}:{actor_id}:{target_id}:yes",
            ),
            InlineKeyboardButton(
                text="❌ Отказать",
                callback_data=f"fs:{kind}:{group_id}:{actor_id}:{target_id}:no",
            ),
        ]
    ])


async def _pending_event(
    session: AsyncSession,
    group_id: int,
    kind: str,
    actor_id: int,
    target_id: int,
) -> GameEvent | None:
    return await session.scalar(
        select(GameEvent).where(
            GameEvent.group_id == group_id,
            GameEvent.event_type == "proposal",
            GameEvent.action == kind,
            GameEvent.actor_telegram_id == actor_id,
            GameEvent.target_telegram_id == target_id,
            GameEvent.outcome == "pending",
        ).order_by(GameEvent.id.desc()).limit(1)
    )


@router.message(
    F.chat.type.in_(GROUP_TYPES),
    F.reply_to_message,
    F.text.casefold().in_(PROPOSAL_ACTIONS),
)
async def social_proposal(message: Message, session: AsyncSession) -> None:
    if message.from_user is None or message.reply_to_message.from_user is None:
        return
    action = " ".join((message.text or "").casefold().strip().split())
    actor = message.from_user
    target = message.reply_to_message.from_user
    if actor.id == target.id:
        await message.reply("Сначала придётся найти второго участника этой истории 😄")
        return
    if target.is_bot:
        await message.reply("Боты пока не вступают в отношения и не принимают вызовы 😄")
        return
    group = await _active_group(session, message.chat.id)
    if group is None:
        return

    kind, template = PROPOSALS[action]
    if kind == "marry":
        actor_marriage = await _active_marriage(session, group.id, actor.id)
        target_marriage = await _active_marriage(session, group.id, target.id)
        if actor_marriage is not None:
            await message.reply("Ты уже состоишь в браке в этой группе. Сначала нужно развестись.")
            return
        if target_marriage is not None:
            await message.reply(f"{_name(target)} уже состоит в браке в этой группе.")
            return

    session.add(GameEvent(
        group_id=group.id,
        event_type="proposal",
        action=kind,
        actor_telegram_id=actor.id,
        target_telegram_id=target.id,
        actor_name=_name(actor),
        target_name=_name(target),
        outcome="pending",
    ))
    await session.commit()
    await message.reply(
        template.format(user1=_name(actor), user2=_name(target)),
        reply_markup=_proposal_markup(kind, group.id, actor.id, target.id),
    )


@router.callback_query(F.data.regexp(r"^fs:(marry|date|love|romance|duel|fight):\d+:\d+:\d+:(yes|no)$"))
async def social_answer(callback: CallbackQuery, session: AsyncSession) -> None:
    _, kind, raw_group, raw_actor, raw_target, decision = callback.data.split(":")
    group_id = int(raw_group)
    actor_id = int(raw_actor)
    target_id = int(raw_target)

    if callback.from_user.id != target_id:
        await callback.answer(FOREIGN_BUTTON_NOTICE, show_alert=True)
        return

    group = await session.scalar(select(Group).where(Group.id == group_id, Group.is_active.is_(True)))
    if group is None or callback.message is None or callback.message.chat.id != group.telegram_chat_id:
        await callback.answer("Эта игра уже недоступна.", show_alert=True)
        return

    event = await _pending_event(session, group_id, kind, actor_id, target_id)
    if event is not None:
        event.outcome = "rejected" if decision == "no" else "accepted"

    if decision == "no":
        if event is not None:
            await session.commit()
        await callback.message.edit_text(
            f"❌ Пользователь {target_id} отклонил {KIND_LABEL[kind]}. Драма окончена. Пока что."
        )
        await callback.answer("Отказано")
        return

    if kind == "marry":
        if await _active_marriage(session, group.id, actor_id) is not None:
            if event is not None:
                event.outcome = "cancelled"
                await session.commit()
            await callback.answer("Автор предложения уже состоит в браке.", show_alert=True)
            return
        if await _active_marriage(session, group.id, target_id) is not None:
            if event is not None:
                event.outcome = "cancelled"
                await session.commit()
            await callback.answer("Вы уже состоите в браке.", show_alert=True)
            return
        first, second = sorted((actor_id, target_id))
        existing = await session.scalar(
            select(GroupMarriage).where(
                GroupMarriage.group_id == group.id,
                GroupMarriage.user1_telegram_id == first,
                GroupMarriage.user2_telegram_id == second,
            )
        )
        if existing is None:
            session.add(GroupMarriage(
                group_id=group.id,
                user1_telegram_id=first,
                user2_telegram_id=second,
                active=True,
            ))
        else:
            existing.active = True
            existing.ended_at = None
        await session.commit()
        await callback.message.edit_text(
            f"💍 Свершилось! {actor_id} и {target_id} теперь официальная семейная пара этой группы. Чат, готовьте дошики на свадьбу."
        )
    elif kind in {"duel", "fight"}:
        await session.commit()
        winner, loser = (actor_id, target_id) if random.randint(0, 1) == 0 else (target_id, actor_id)
        flavor = random.choice([
            "Победитель определился после трёх секунд очень серьёзной суеты.",
            "Судьи ничего не поняли, но победителя уже объявили.",
            "Решающим приёмом оказался грозный взгляд и абсолютная уверенность.",
        ])
        await callback.message.edit_text(
            f"{'⚔️ Дуэль' if kind == 'duel' else '🥊 Драка'} состоялась! Победитель: {winner}. Проигравший: {loser}. {flavor}"
        )
    elif kind == "date":
        await session.commit()
        await callback.message.edit_text(
            f"🌹 Свидание принято! {actor_id} и {target_id}, чат требует потом отчёт: было ли хотя бы два бургера."
        )
    elif kind == "love":
        await session.commit()
        await callback.message.edit_text(
            f"❤️ {target_id} принял признание {actor_id}. Кажется, в этой группе только что стало на одну историю больше."
        )
    else:
        await session.commit()
        await callback.message.edit_text(
            f"😏 {target_id} принял романтическое предложение {actor_id}. Дальнейшие подробности остаются за пределами протокола Mimoru."
        )
    await callback.answer("Принято")


@router.message(F.chat.type.in_(GROUP_TYPES), F.text.casefold() == "развестись")
async def divorce(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    group = await _active_group(session, message.chat.id)
    if group is None:
        return
    marriage = await _active_marriage(session, group.id, message.from_user.id)
    if marriage is None:
        await message.reply("Ты не состоишь в браке в этой группе.")
        return
    partner = (
        marriage.user2_telegram_id
        if marriage.user1_telegram_id == message.from_user.id
        else marriage.user1_telegram_id
    )
    marriage.active = False
    marriage.ended_at = datetime.now(timezone.utc)
    await session.commit()
    await message.reply(
        f"💔 {message.from_user.id} развёлся с {partner}. Дети остаются у админа, роутер делить не будем."
    )


@router.message(F.chat.type.in_(GROUP_TYPES), F.text.casefold().in_({"мой брак", "брак"}))
async def my_marriage(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    group = await _active_group(session, message.chat.id)
    if group is None:
        return
    marriage = await _active_marriage(session, group.id, message.from_user.id)
    if marriage is None:
        await message.reply("💍 В этой группе ты пока свободен.")
        return
    partner = (
        marriage.user2_telegram_id
        if marriage.user1_telegram_id == message.from_user.id
        else marriage.user1_telegram_id
    )
    await message.reply(f"💍 Твой партнёр в этой группе: {partner}. Берегите семейный Wi-Fi.")


def _history_markup(owner_id: int, kind: str, page: int, pages: int) -> InlineKeyboardMarkup | None:
    if pages <= 1:
        return None
    buttons: list[InlineKeyboardButton] = []
    if page > 0:
        buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"fsh:{owner_id}:{kind}:{page - 1}"))
    if page + 1 < pages:
        buttons.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"fsh:{owner_id}:{kind}:{page + 1}"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None


async def _history_text(session: AsyncSession, group: Group, kind: str, page: int) -> tuple[str, int, int]:
    if kind == "marry":
        total = int(await session.scalar(
            select(func.count(GroupMarriage.id)).where(
                GroupMarriage.group_id == group.id,
                GroupMarriage.active.is_(True),
            )
        ) or 0)
        pages = max(1, math.ceil(total / HISTORY_PAGE_SIZE))
        page = max(0, min(page, pages - 1))
        rows = list((await session.scalars(
            select(GroupMarriage).where(
                GroupMarriage.group_id == group.id,
                GroupMarriage.active.is_(True),
            ).order_by(GroupMarriage.created_at.desc()).offset(page * HISTORY_PAGE_SIZE).limit(HISTORY_PAGE_SIZE)
        )).all())
        lines = [
            f"• {row.user1_telegram_id} ❤️ {row.user2_telegram_id} · с {row.created_at:%d.%m.%Y}"
            for row in rows
        ]
        body = "\n".join(lines) if lines else "В этой группе пока нет активных браков."
        return f"{HISTORY_TITLES[kind]}\n\n{body}\n\nВсего активных браков: {total}", page, pages

    total = int(await session.scalar(
        select(func.count(GameEvent.id)).where(
            GameEvent.group_id == group.id,
            GameEvent.event_type == "proposal",
            GameEvent.action == kind,
            GameEvent.outcome == "accepted",
        )
    ) or 0)
    pages = max(1, math.ceil(total / HISTORY_PAGE_SIZE))
    page = max(0, min(page, pages - 1))
    rows = list((await session.scalars(
        select(GameEvent).where(
            GameEvent.group_id == group.id,
            GameEvent.event_type == "proposal",
            GameEvent.action == kind,
            GameEvent.outcome == "accepted",
        ).order_by(GameEvent.created_at.desc()).offset(page * HISTORY_PAGE_SIZE).limit(HISTORY_PAGE_SIZE)
    )).all())
    icon = "🥊" if kind == "fight" else "⚔️" if kind == "duel" else "🌹" if kind == "date" else "❤️"
    lines = [f"• {icon} {row.actor_name} → {row.target_name} · {row.created_at:%d.%m %H:%M}" for row in rows]
    body = "\n".join(lines) if lines else "Таких событий в этой группе пока не было."
    return f"{HISTORY_TITLES[kind]}\n\n{body}\n\nВсего: {total}", page, pages


@router.message(F.chat.type.in_(GROUP_TYPES), F.text.casefold().in_(HISTORY_WORDS))
async def game_history(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    group = await _active_group(session, message.chat.id)
    if group is None:
        return
    kind = HISTORY_COMMANDS[(message.text or "").casefold().strip()]
    text, page, pages = await _history_text(session, group, kind, 0)
    await message.reply(text, reply_markup=_history_markup(message.from_user.id, kind, page, pages))


@router.callback_query(F.data.regexp(r"^fsh:\d+:(marry|fight|duel|date|love|romance):\d+$"))
async def game_history_page(callback: CallbackQuery, session: AsyncSession) -> None:
    _, raw_owner, kind, raw_page = (callback.data or "").split(":")
    if callback.from_user.id != int(raw_owner):
        await callback.answer(FOREIGN_BUTTON_NOTICE, show_alert=True)
        return
    if callback.message is None:
        await callback.answer()
        return
    group = await _active_group(session, callback.message.chat.id)
    if group is None:
        await callback.answer("Эта группа больше недоступна для Mimoru.", show_alert=True)
        return
    text, page, pages = await _history_text(session, group, kind, int(raw_page))
    await callback.message.edit_text(text, reply_markup=_history_markup(callback.from_user.id, kind, page, pages))
    await callback.answer()


@router.message(F.chat.type.in_(GROUP_TYPES), F.text.casefold() == "стата игр")
async def game_statistics(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    group = await _active_group(session, message.chat.id)
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
        f"🤝 Примирений: {action_counts.get('помириться', 0)}\n\n"
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
        summary += "\n\nСтатистика начнёт заполняться после первого игрового действия."

    await message.reply(summary)
