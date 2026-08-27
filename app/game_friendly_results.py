from __future__ import annotations

import random
import re
import time
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, MessageEntity
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.fun_models import GameEvent, GroupMarriage
from app.db.models import Group, User
from app.game_contracts import PROPOSALS, PROPOSAL_ACTIONS
from app.handlers.fun_commands import FUN_ACTIONS

router = Router(name=__name__)
GROUP_TYPES = {"group", "supergroup"}
ACTION_COOLDOWN_SECONDS = 3.0
_action_cooldowns: dict[tuple[int, int], float] = {}
_last_variant: dict[tuple[int, int, str], int] = {}
FOREIGN_BUTTON_NOTICE = "Эти кнопки предназначены другому участнику 🙂"

ACTION_EMOJI = {
    "обнять": "🫂", "поцеловать": "💋", "засосать": "😘", "подкатить": "😏",
    "сделать комплимент": "✨", "погладить": "🤗", "пощекотать": "😂",
    "пнуть": "🦵", "пнуть под зад": "🦵", "дать леща": "👋", "дать подзатыльник": "🤚",
    "ударить": "👊", "укусить": "🦷", "покусать": "🦷", "ограбить": "💰",
    "похитить": "🕵️", "суд": "⚖️", "арестовать": "🚓", "превратить в кота": "🐈",
    "превратить в жабу": "🐸", "превратить в дошик": "🍜", "дать дошик": "🍜",
    "накормить": "🍕", "украсть сердце": "💘", "поссориться": "💢", "помириться": "🤝",
    "похвалить": "👏", "уважить": "🤝", "проклясть": "🔮", "взорвать": "💥",
    "воскресить": "✨", "заморозить": "🧊", "благословить": "🙏", "загуглить": "🔎",
}
DEFAULT_EMOJIS = ("🎭", "😄", "✨", "🎲", "😎", "🔥")
ACTION_VARIANTS = (
    "{emoji} {actor} → {target}: «{action}». Засчитано!",
    "{emoji} {actor} выбрал для {target}: «{action}» 😄",
    "{emoji} {target}, внимание: {actor} использует «{action}»!",
    "{emoji} Сегодня у {actor} план — «{action}» для {target} 😏",
    "{emoji} {actor} + {target}: действие момента — «{action}».",
    "{emoji} {actor} применяет к {target} «{action}». Эффект есть!",
)
PROPOSAL_TEMPLATES = {
    "marry": ("💍 {actor} делает предложение {target}. Свадьбе быть?", "💒 {actor} зовёт {target} под виртуальный венец. Решение за тобой!", "🥂 {target}, у {actor} серьёзный вопрос: поженимся?"),
    "date": ("🌹 {actor} зовёт {target} на свидание. Принимаешь?", "☕ {target}, {actor} приглашает тебя на свидание. Как тебе идея?", "💐 {actor} предлагает {target} провести время вдвоём. Ответ за тобой!"),
    "love": ("❤️ {actor} признаётся {target} в любви. Чат замер…", "💖 {target}, кажется, {actor} давно хотел сказать: люблю!", "🥰 {actor} открыл сердце перед {target}. Что ответишь?"),
    "romance": ("😏 {actor} предлагает {target} романтический вечер. Решение за тобой.", "💞 {actor} зовёт {target} добавить немного романтики. Согласен?", "🌙 {target}, у {actor} для тебя романтическое предложение."),
    "duel": ("⚔️ {actor} вызывает {target} на дуэль. Принимаешь?", "🗡️ {target}, перчатка брошена: {actor} ждёт дуэль!", "⚔️ {actor} против {target}. Но сначала — согласие на дуэль."),
    "fight": ("🥊 {actor} вызывает {target} на драку. Принимаешь?", "👊 {target}, {actor} предлагает эпическую драку!", "🥊 {actor} vs {target}. В бой или отбой?"),
}
RESULT_VARIANTS = {
    "marry": ("💍 {actor} и {target} теперь пара этой группы! Горько! 🎉", "💒 Свершилось: {actor} + {target} = ❤️. Чат готовит свадьбу!", "🥂 {actor} и {target} сказали друг другу «да». Поздравляем!"),
    "date": ("🌹 {actor} и {target} идут на свидание. Хорошего вечера!", "☕ Свидание принято: {actor} + {target}. Ждём хорошие новости 😄", "💐 {target} согласился на свидание с {actor}. Романтика пошла!"),
    "love": ("❤️ {target} принял признание {actor}. Милота зашкаливает!", "💖 Признание принято! {actor} и {target}, берегите эту историю.", "🥰 {target} ответил взаимностью на признание {actor}. Красиво!"),
    "romance": ("💞 {target} принял предложение {actor}. Дальше без протокола 😏", "🌙 Романтика одобрена: {actor} и {target}. Хорошего вечера!", "😏 {target} сказал «да» {actor}. Остальное чат додумывает сам."),
}
TOKEN_RE = re.compile(r"\{(actor|target|winner|loser)\}")


def _utf16_len(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def _tg_name(user) -> str:
    full_name = (getattr(user, "full_name", None) or "").strip()
    if full_name:
        return full_name
    if getattr(user, "username", None):
        return f"@{user.username}"
    return "участник"


def _pick_variant(key: tuple[int, int, str], variants: tuple[str, ...]) -> str:
    previous = _last_variant.get(key)
    choices = [idx for idx in range(len(variants)) if idx != previous] or list(range(len(variants)))
    idx = random.choice(choices)
    _last_variant[key] = idx
    return variants[idx]


def _render(template: str, mentions: dict[str, tuple[str, int]], **plain: str) -> tuple[str, list[MessageEntity]]:
    template = template.format(**{key: "{" + key + "}" for key in mentions}, **plain)
    chunks: list[str] = []
    entities: list[MessageEntity] = []
    cursor = 0
    for match in TOKEN_RE.finditer(template):
        chunks.append(template[cursor:match.start()])
        name, user_id = mentions[match.group(1)]
        prefix = "".join(chunks)
        chunks.append(name)
        entities.append(MessageEntity(type="text_link", offset=_utf16_len(prefix), length=_utf16_len(name), url=f"tg://user?id={user_id}"))
        cursor = match.end()
    chunks.append(template[cursor:])
    return "".join(chunks), entities


async def _db_name(session: AsyncSession, user_id: int, fallback: str | None = None) -> str:
    user = await session.scalar(select(User).where(User.telegram_id == user_id))
    if user is not None:
        name = " ".join(part for part in (user.first_name, user.last_name) if part).strip()
        if name:
            return name
        if user.username:
            return f"@{user.username}"
    if fallback and fallback.strip() and not fallback.strip().isdigit():
        return fallback.strip()
    return "участник"


async def _active_group(session: AsyncSession, chat_id: int, *, for_update: bool = False) -> Group | None:
    query = select(Group).where(Group.telegram_chat_id == chat_id, Group.is_active.is_(True))
    if for_update:
        query = query.with_for_update()
    return await session.scalar(query)


def _proposal_markup(kind: str, group_id: int, actor_id: int, target_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Принять", callback_data=f"fsfriendly:{kind}:{group_id}:{actor_id}:{target_id}:yes"), InlineKeyboardButton(text="❌ Отказать", callback_data=f"fsfriendly:{kind}:{group_id}:{actor_id}:{target_id}:no")]])


@router.message(F.chat.type.in_(GROUP_TYPES), F.reply_to_message, F.text.casefold().in_(FUN_ACTIONS))
async def friendly_fun_action(message: Message, session: AsyncSession) -> None:
    if message.from_user is None or message.reply_to_message.from_user is None:
        return
    actor, target = message.from_user, message.reply_to_message.from_user
    if target.is_bot:
        return
    if actor.id == target.id:
        await message.reply("😄 С собой это действие выглядит слишком подозрительно.")
        return
    key = (message.chat.id, actor.id)
    now = time.monotonic()
    if now - _action_cooldowns.get(key, 0.0) < ACTION_COOLDOWN_SECONDS:
        await message.reply("⏳ Подожди 3 секунды до следующего действия 😄")
        return
    _action_cooldowns[key] = now
    action = " ".join((message.text or "").casefold().strip().split())
    variant = _pick_variant((message.chat.id, actor.id, action), ACTION_VARIANTS)
    text, entities = _render(variant, {"actor": (_tg_name(actor), actor.id), "target": (_tg_name(target), target.id)}, emoji=ACTION_EMOJI.get(action, random.choice(DEFAULT_EMOJIS)), action=action)
    await message.reply(text, entities=entities)
    group = await _active_group(session, message.chat.id)
    if group is not None:
        session.add(GameEvent(group_id=group.id, event_type="action", action=action, actor_telegram_id=actor.id, target_telegram_id=target.id, actor_name=_tg_name(actor), target_name=_tg_name(target), outcome="done"))
        await session.commit()


@router.message(F.chat.type.in_(GROUP_TYPES), F.reply_to_message, F.text.casefold().in_(PROPOSAL_ACTIONS))
async def friendly_proposal(message: Message, session: AsyncSession) -> None:
    if message.from_user is None or message.reply_to_message.from_user is None:
        return
    actor, target = message.from_user, message.reply_to_message.from_user
    if actor.id == target.id:
        await message.reply("😄 Для этой истории нужен второй участник.")
        return
    if target.is_bot:
        await message.reply("🤖 Боты пока не принимают такие предложения.")
        return
    action = " ".join((message.text or "").casefold().strip().split())
    kind = PROPOSALS[action][0]
    group = await _active_group(session, message.chat.id, for_update=kind == "marry")
    if group is None:
        return
    if kind == "marry":
        occupied = await session.scalar(select(GroupMarriage.id).where(GroupMarriage.group_id == group.id, GroupMarriage.active.is_(True), or_(GroupMarriage.user1_telegram_id.in_((actor.id, target.id)), GroupMarriage.user2_telegram_id.in_((actor.id, target.id)))).limit(1))
        if occupied is not None:
            await message.reply("💍 Кто-то из вас уже состоит в браке в этой группе.")
            return
    actor_name, target_name = _tg_name(actor), _tg_name(target)
    session.add(GameEvent(group_id=group.id, event_type="proposal", action=kind, actor_telegram_id=actor.id, target_telegram_id=target.id, actor_name=actor_name, target_name=target_name, outcome="pending"))
    await session.commit()
    template = _pick_variant((message.chat.id, actor.id, f"proposal:{kind}"), PROPOSAL_TEMPLATES[kind])
    text, entities = _render(template, {"actor": (actor_name, actor.id), "target": (target_name, target.id)})
    await message.reply(text, entities=entities, reply_markup=_proposal_markup(kind, group.id, actor.id, target.id))


@router.callback_query(F.data.regexp(r"^fsfriendly:(marry|date|love|romance|duel|fight):\d+:\d+:\d+:(yes|no)$"))
async def friendly_answer(callback: CallbackQuery, session: AsyncSession) -> None:
    _, kind, raw_group, raw_actor, raw_target, decision = (callback.data or "").split(":")
    group_id, actor_id, target_id = int(raw_group), int(raw_actor), int(raw_target)
    if callback.from_user.id != target_id:
        await callback.answer(FOREIGN_BUTTON_NOTICE, show_alert=True)
        return
    group = await session.scalar(select(Group).where(Group.id == group_id, Group.is_active.is_(True)).with_for_update())
    if group is None or callback.message is None or callback.message.chat.id != group.telegram_chat_id:
        await callback.answer("Эта игра уже недоступна.", show_alert=True)
        return
    event = await session.scalar(select(GameEvent).where(GameEvent.group_id == group_id, GameEvent.event_type == "proposal", GameEvent.action == kind, GameEvent.actor_telegram_id == actor_id, GameEvent.target_telegram_id == target_id, GameEvent.outcome == "pending").order_by(GameEvent.id.desc()).limit(1).with_for_update())
    if event is None:
        await callback.answer("На это предложение уже ответили.", show_alert=True)
        return
    actor_name = await _db_name(session, actor_id, event.actor_name)
    target_name = await _db_name(session, target_id, event.target_name or _tg_name(callback.from_user))
    mentions = {"actor": (actor_name, actor_id), "target": (target_name, target_id)}
    event.outcome = "accepted" if decision == "yes" else "rejected"
    if decision == "no":
        await session.commit()
        rejects = ("❌ {target} отказал {actor}. Без обид — игра продолжается 😄", "🙅 {target} сказал «не сегодня», {actor}. Бывает!", "😅 {actor}, {target} отклонил предложение. Следующая попытка будет легендарной.")
        text, entities = _render(random.choice(rejects), mentions)
        await callback.message.edit_text(text, entities=entities)
        await callback.answer("Отказано")
        return
    if kind == "marry":
        occupied = await session.scalar(select(GroupMarriage.id).where(GroupMarriage.group_id == group.id, GroupMarriage.active.is_(True), or_(GroupMarriage.user1_telegram_id.in_((actor_id, target_id)), GroupMarriage.user2_telegram_id.in_((actor_id, target_id)))).limit(1))
        if occupied is not None:
            event.outcome = "cancelled"
            await session.commit()
            await callback.answer("Кто-то из участников уже состоит в браке.", show_alert=True)
            return
        first, second = sorted((actor_id, target_id))
        existing = await session.scalar(select(GroupMarriage).where(GroupMarriage.group_id == group.id, GroupMarriage.user1_telegram_id == first, GroupMarriage.user2_telegram_id == second))
        if existing is None:
            session.add(GroupMarriage(group_id=group.id, user1_telegram_id=first, user2_telegram_id=second, active=True))
        else:
            existing.active, existing.ended_at = True, None
        await session.commit()
        template = random.choice(RESULT_VARIANTS["marry"])
        text, entities = _render(template, mentions)
    elif kind in {"duel", "fight"}:
        await session.commit()
        winner_id, loser_id = (actor_id, target_id) if random.randint(0, 1) == 0 else (target_id, actor_id)
        winner_name = actor_name if winner_id == actor_id else target_name
        loser_name = target_name if loser_id == target_id else actor_name
        variants = ("⚔️ Победитель: {winner}! {loser} требует реванш 😄" if kind == "duel" else "🥊 {winner} побеждает! {loser} уже готовит реванш 😄", "🏆 {winner} забирает победу. {loser}, достойная битва!", "🔥 Вот это бой! {winner} победил, {loser} — красавчик за участие.")
        text, entities = _render(random.choice(variants), {"winner": (winner_name, winner_id), "loser": (loser_name, loser_id)})
    else:
        await session.commit()
        text, entities = _render(random.choice(RESULT_VARIANTS[kind]), mentions)
    await callback.message.edit_text(text, entities=entities)
    await callback.answer("Принято")


@router.message(F.chat.type.in_(GROUP_TYPES), F.text.casefold() == "развестись")
async def friendly_divorce(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    group = await _active_group(session, message.chat.id, for_update=True)
    if group is None:
        return
    marriage = await session.scalar(select(GroupMarriage).where(GroupMarriage.group_id == group.id, GroupMarriage.active.is_(True), or_(GroupMarriage.user1_telegram_id == message.from_user.id, GroupMarriage.user2_telegram_id == message.from_user.id)).with_for_update())
    if marriage is None:
        await message.reply("💍 В этой группе ты сейчас не в браке.")
        return
    partner_id = marriage.user2_telegram_id if marriage.user1_telegram_id == message.from_user.id else marriage.user1_telegram_id
    partner_name = await _db_name(session, partner_id)
    marriage.active = False
    marriage.ended_at = datetime.now(timezone.utc)
    await session.commit()
    variants = ("💔 {actor} и {target} теперь свободны. Без делёжки Wi‑Fi 😄", "💔 Брак завершён: {actor} и {target}. Жизнь продолжается!", "🕊️ {actor} и {target} мирно разошлись. Чат желает удачи обоим.")
    text, entities = _render(random.choice(variants), {"actor": (_tg_name(message.from_user), message.from_user.id), "target": (partner_name, partner_id)})
    await message.reply(text, entities=entities)


@router.message(F.chat.type.in_(GROUP_TYPES), F.text.casefold().in_({"мой брак", "брак"}))
async def friendly_marriage(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    group = await _active_group(session, message.chat.id)
    if group is None:
        return
    marriage = await session.scalar(select(GroupMarriage).where(GroupMarriage.group_id == group.id, GroupMarriage.active.is_(True), or_(GroupMarriage.user1_telegram_id == message.from_user.id, GroupMarriage.user2_telegram_id == message.from_user.id)))
    if marriage is None:
        await message.reply("💍 В этой группе ты пока свободен 😄")
        return
    partner_id = marriage.user2_telegram_id if marriage.user1_telegram_id == message.from_user.id else marriage.user1_telegram_id
    partner_name = await _db_name(session, partner_id)
    text, entities = _render("💍 Твоя пара в этой группе — {target} ❤️", {"target": (partner_name, partner_id)})
    await message.reply(text, entities=entities)
