from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group
from app.games.panels import ensure_game_panel, render_profile, render_rating
from app.games.registry import game_registry


router = Router(name=__name__)
GROUP_TYPES = {"group", "supergroup"}


async def _active_group(session: AsyncSession, chat_id: int) -> Group | None:
    return await session.scalar(
        select(Group).where(
            Group.telegram_chat_id == chat_id,
            Group.is_active.is_(True),
        )
    )


def _games_markup() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for definition in game_registry.all():
        rows.append([
            InlineKeyboardButton(
                text=definition.title,
                callback_data=f"gm:new:{definition.code}",
            )
        ])
    rows.append([InlineKeyboardButton(text="◀️ В игровой центр", callback_data="gm:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _games_text() -> str:
    definitions = game_registry.all()
    if not definitions:
        return (
            "🎮 ВЫБОР ИГРЫ\n\n"
            "Игровое ядро готовится к подключению первой полноценной игры.\n"
            "Старые развлекательные команды сюда больше не относятся."
        )
    lines = ["🎮 ВЫБОР ИГРЫ", ""]
    for definition in definitions:
        lines.append(
            f"{definition.title} · {definition.min_players}–{definition.max_players} игроков"
        )
    lines.append("\nВыберите игру кнопкой ниже.")
    return "\n".join(lines)


@router.message(Command("games"), F.chat.type.in_(GROUP_TYPES))
async def games_command(message: Message, bot: Bot, session: AsyncSession) -> None:
    group = await _active_group(session, message.chat.id)
    if group is None:
        return
    await ensure_game_panel(bot, session, group=group)


@router.callback_query(F.data == "gm:home")
async def game_home(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    if callback.message is None:
        await callback.answer("Игровая панель недоступна.", show_alert=True)
        return
    group = await _active_group(session, callback.message.chat.id)
    if group is None:
        await callback.answer("Группа больше не подключена к Mimoru.", show_alert=True)
        return
    await ensure_game_panel(bot, session, group=group, pin=False)
    await callback.answer()


@router.callback_query(F.data == "gm:list")
async def game_list(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer("Игровая панель недоступна.", show_alert=True)
        return
    await callback.message.edit_text(_games_text(), reply_markup=_games_markup())
    await callback.answer()


@router.callback_query(F.data == "gm:profile")
async def game_profile(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.message is None:
        await callback.answer("Игровая панель недоступна.", show_alert=True)
        return
    group = await _active_group(session, callback.message.chat.id)
    if group is None:
        await callback.answer("Группа больше не подключена к Mimoru.", show_alert=True)
        return
    name = (callback.from_user.full_name or callback.from_user.username or "Игрок").strip()
    text = await render_profile(
        session,
        group_id=group.id,
        user_id=callback.from_user.id,
        name=name,
    )
    await callback.answer(text, show_alert=True)


@router.callback_query(F.data == "gm:rating")
async def game_rating(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.message is None:
        await callback.answer("Игровая панель недоступна.", show_alert=True)
        return
    group = await _active_group(session, callback.message.chat.id)
    if group is None:
        await callback.answer("Группа больше не подключена к Mimoru.", show_alert=True)
        return
    text = await render_rating(session, group_id=group.id)
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ В игровой центр", callback_data="gm:home")]]
    )
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data == "gm:rules:all")
async def game_rules(callback: CallbackQuery) -> None:
    await callback.answer(
        "Игры работают внутри группы кнопками. Обычная переписка не считается игровым вводом. В одной группе одновременно запускается одна групповая игра.",
        show_alert=True,
    )


@router.callback_query(F.data.regexp(r"^gm:rules:[a-z0-9_]{1,32}$"))
async def game_specific_rules(callback: CallbackQuery) -> None:
    code = (callback.data or "").rsplit(":", 1)[-1]
    definition = game_registry.get(code)
    if definition is None:
        await callback.answer("Эта игра больше не доступна.", show_alert=True)
        return
    await callback.answer(
        f"{definition.title}: правила появятся вместе с реализацией игры.",
        show_alert=True,
    )


@router.callback_query(F.data.regexp(r"^gm:new:[a-z0-9_]{1,32}$"))
async def game_create_not_yet_connected(callback: CallbackQuery) -> None:
    code = (callback.data or "").rsplit(":", 1)[-1]
    if game_registry.get(code) is None:
        await callback.answer("Эта игра больше не доступна.", show_alert=True)
        return
    await callback.answer("Игровое лобби подключается на следующем этапе.", show_alert=True)


@router.callback_query(F.data.regexp(r"^gm:open:\d+$"))
async def game_open(callback: CallbackQuery) -> None:
    await callback.answer("Текущее игровое состояние откроется здесь после подключения первой игры.", show_alert=True)
