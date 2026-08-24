from __future__ import annotations

import math

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, MessageEntity
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.fun_models import GameEvent, GroupMarriage
from app.db.models import Group, User
from app.handlers.fun_social import HISTORY_COMMANDS, HISTORY_TITLES, HISTORY_WORDS

router = Router(name=__name__)
GROUP_TYPES = {"group", "supergroup"}
PAGE_SIZE = 8


def _utf16_len(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


async def _name(session: AsyncSession, user_id: int, fallback: str | None = None) -> str:
    user = await session.scalar(select(User).where(User.telegram_id == user_id))
    if user is not None:
        full = " ".join(part for part in (user.first_name, user.last_name) if part).strip()
        if full:
            return full
        if user.username:
            return f"@{user.username}"
    if fallback and fallback.strip() and not fallback.strip().isdigit():
        return fallback.strip()
    return "участник"


def _append_mention(text: str, entities: list[MessageEntity], name: str, user_id: int) -> str:
    offset = _utf16_len(text)
    entities.append(MessageEntity(type="text_link", offset=offset, length=_utf16_len(name), url=f"tg://user?id={user_id}"))
    return text + name


def _markup(owner_id: int, kind: str, page: int, pages: int) -> InlineKeyboardMarkup | None:
    if pages <= 1:
        return None
    row: list[InlineKeyboardButton] = []
    if page > 0:
        row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"fshfriendly:{owner_id}:{kind}:{page - 1}"))
    if page + 1 < pages:
        row.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"fshfriendly:{owner_id}:{kind}:{page + 1}"))
    return InlineKeyboardMarkup(inline_keyboard=[row])


async def _history(session: AsyncSession, group: Group, kind: str, page: int) -> tuple[str, list[MessageEntity], int, int]:
    entities: list[MessageEntity] = []
    if kind == "marry":
        total = int(await session.scalar(select(func.count(GroupMarriage.id)).where(GroupMarriage.group_id == group.id, GroupMarriage.active.is_(True))) or 0)
        pages = max(1, math.ceil(total / PAGE_SIZE)); page = max(0, min(page, pages - 1))
        rows = list((await session.scalars(select(GroupMarriage).where(GroupMarriage.group_id == group.id, GroupMarriage.active.is_(True)).order_by(GroupMarriage.created_at.desc()).offset(page * PAGE_SIZE).limit(PAGE_SIZE))).all())
        text = HISTORY_TITLES[kind] + "\n\n"
        if not rows:
            text += "В этой группе пока нет активных браков."
        for row in rows:
            text += "• "
            text = _append_mention(text, entities, await _name(session, row.user1_telegram_id), row.user1_telegram_id)
            text += " ❤️ "
            text = _append_mention(text, entities, await _name(session, row.user2_telegram_id), row.user2_telegram_id)
            text += f" · с {row.created_at:%d.%m.%Y}\n"
        text += f"\nВсего активных браков: {total}"
        return text, entities, page, pages

    total = int(await session.scalar(select(func.count(GameEvent.id)).where(GameEvent.group_id == group.id, GameEvent.event_type == "proposal", GameEvent.action == kind, GameEvent.outcome == "accepted")) or 0)
    pages = max(1, math.ceil(total / PAGE_SIZE)); page = max(0, min(page, pages - 1))
    rows = list((await session.scalars(select(GameEvent).where(GameEvent.group_id == group.id, GameEvent.event_type == "proposal", GameEvent.action == kind, GameEvent.outcome == "accepted").order_by(GameEvent.created_at.desc()).offset(page * PAGE_SIZE).limit(PAGE_SIZE))).all())
    icon = "🥊" if kind == "fight" else "⚔️" if kind == "duel" else "🌹" if kind == "date" else "❤️"
    text = HISTORY_TITLES[kind] + "\n\n"
    if not rows:
        text += "Таких событий в этой группе пока не было."
    for row in rows:
        text += f"• {icon} "
        text = _append_mention(text, entities, await _name(session, row.actor_telegram_id, row.actor_name), row.actor_telegram_id)
        text += " → "
        text = _append_mention(text, entities, await _name(session, row.target_telegram_id, row.target_name), row.target_telegram_id)
        text += f" · {row.created_at:%d.%m %H:%M}\n"
    text += f"\nВсего: {total}"
    return text, entities, page, pages


async def _group(session: AsyncSession, chat_id: int) -> Group | None:
    return await session.scalar(select(Group).where(Group.telegram_chat_id == chat_id, Group.is_active.is_(True)))


@router.message(F.chat.type.in_(GROUP_TYPES), F.text.casefold().in_(HISTORY_WORDS))
async def friendly_history(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    group = await _group(session, message.chat.id)
    if group is None:
        return
    kind = HISTORY_COMMANDS[(message.text or "").casefold().strip()]
    text, entities, page, pages = await _history(session, group, kind, 0)
    await message.reply(text, entities=entities, reply_markup=_markup(message.from_user.id, kind, page, pages))


@router.callback_query(F.data.regexp(r"^fshfriendly:\d+:(marry|fight|duel|date|love|romance):\d+$"))
async def friendly_history_page(callback: CallbackQuery, session: AsyncSession) -> None:
    _, raw_owner, kind, raw_page = (callback.data or "").split(":")
    if callback.from_user.id != int(raw_owner):
        await callback.answer("Это меню открыл другой участник 🙂", show_alert=True)
        return
    if callback.message is None:
        await callback.answer(); return
    group = await _group(session, callback.message.chat.id)
    if group is None:
        await callback.answer("Эта группа больше недоступна.", show_alert=True); return
    text, entities, page, pages = await _history(session, group, kind, int(raw_page))
    await callback.message.edit_text(text, entities=entities, reply_markup=_markup(callback.from_user.id, kind, page, pages))
    await callback.answer()
