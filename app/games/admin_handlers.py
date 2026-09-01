from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GameSession
from app.db.models import Group
from app.games.enums import ACTIVE_SESSION_STATUSES
from app.games.manager import GameManager
from app.games.messages import retire_active_messages
from app.games.panels import ensure_game_panel
from app.games.registry import game_registry
from app.services.access import can_manage_group


router = Router(name=__name__)
GROUP_TYPES = {"group", "supergroup"}
manager = GameManager()


async def _active_group(session: AsyncSession, chat_id: int) -> Group | None:
    return await session.scalar(
        select(Group).where(
            Group.telegram_chat_id == chat_id,
            Group.is_active.is_(True),
        )
    )


def _admin_text(game: GameSession | None) -> str:
    if game is None:
        return (
            "🛠 УПРАВЛЕНИЕ ИГРАМИ\n\n"
            "🟢 Активной игры нет.\n\n"
            "Можно восстановить основную игровую панель, если её удалили или она перестала обновляться."
        )
    definition = game_registry.get(game.game_type)
    title = definition.title if definition is not None else game.game_type
    return (
        "🛠 УПРАВЛЕНИЕ ИГРАМИ\n\n"
        f"🔴 Активная сессия: {title}\n"
        f"Статус: {game.status}\n"
        f"Фаза: {game.phase}\n"
        f"Раунд: {game.round_no}\n\n"
        "Принудительная отмена аварийно закрывает сессию без начисления побед и рейтинга."
    )


def _admin_markup(group_id: int, requester_id: int, game: GameSession | None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="♻️ Восстановить панель",
                callback_data=f"gm:adm:panel:{group_id}:{requester_id}",
            )
        ]
    ]
    if game is not None:
        rows.append([
            InlineKeyboardButton(
                text="🛑 Отменить активную игру",
                callback_data=f"gm:adm:cancel:{game.id}:{requester_id}",
            )
        ])
    rows.append([
        InlineKeyboardButton(
            text="❌ Закрыть",
            callback_data=f"gm:adm:close:{group_id}:{requester_id}",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _confirm_markup(game_id: int, requester_id: int, group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🛑 Да, отменить игру",
                callback_data=f"gm:adm:confirm:{game_id}:{requester_id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=f"gm:adm:back:{group_id}:{requester_id}",
            )
        ],
    ])


async def _managed_group_for_callback(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
    *,
    group_id: int,
    requester_id: int,
) -> Group | None:
    if callback.message is None:
        return None
    if callback.from_user.id != requester_id:
        await callback.answer("Эта служебная карточка открыта другим управляющим.", show_alert=True)
        return None
    group = await session.get(Group, group_id)
    if (
        group is None
        or not group.is_active
        or callback.message.chat.id != group.telegram_chat_id
    ):
        await callback.answer("Группа больше не активна.", show_alert=True)
        return None
    if not await can_manage_group(bot, group, callback.from_user.id, session):
        await callback.answer("❌ Управление играми доступно только управляющим группы.", show_alert=True)
        return None
    return group


async def _render_admin(
    callback: CallbackQuery,
    session: AsyncSession,
    *,
    group: Group,
    requester_id: int,
) -> None:
    if callback.message is None:
        return
    game = await manager.get_active_game(session, group_id=group.id)
    try:
        await callback.message.edit_text(
            _admin_text(game),
            reply_markup=_admin_markup(group.id, requester_id, game),
        )
    except TelegramBadRequest as error:
        if "message is not modified" not in str(error).casefold():
            raise


@router.message(Command("game_admin"), F.chat.type.in_(GROUP_TYPES))
async def game_admin_command(message: Message, bot: Bot, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    group = await _active_group(session, message.chat.id)
    if group is None:
        return
    if not await can_manage_group(bot, group, message.from_user.id, session):
        await message.answer("❌ Управление играми доступно только управляющим группы.")
        return
    game = await manager.get_active_game(session, group_id=group.id)
    await message.answer(
        _admin_text(game),
        reply_markup=_admin_markup(group.id, message.from_user.id, game),
    )


@router.callback_query(F.data.regexp(r"^gm:adm:panel:\d+:\d+$"))
async def game_admin_restore_panel(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    _, _, _, group_raw, requester_raw = (callback.data or "").split(":")
    group = await _managed_group_for_callback(
        callback,
        bot,
        session,
        group_id=int(group_raw),
        requester_id=int(requester_raw),
    )
    if group is None:
        return
    await ensure_game_panel(bot, session, group=group, pin=True)
    await _render_admin(callback, session, group=group, requester_id=int(requester_raw))
    await callback.answer("♻️ Игровая панель восстановлена")


@router.callback_query(F.data.regexp(r"^gm:adm:back:\d+:\d+$"))
async def game_admin_back(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    _, _, _, group_raw, requester_raw = (callback.data or "").split(":")
    group = await _managed_group_for_callback(
        callback,
        bot,
        session,
        group_id=int(group_raw),
        requester_id=int(requester_raw),
    )
    if group is None:
        return
    await _render_admin(callback, session, group=group, requester_id=int(requester_raw))
    await callback.answer()


@router.callback_query(F.data.regexp(r"^gm:adm:cancel:\d+:\d+$"))
async def game_admin_cancel_prompt(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    if callback.message is None:
        return
    _, _, _, game_raw, requester_raw = (callback.data or "").split(":")
    game = await manager.get_game(session, game_id=int(game_raw))
    if game is None or game.status not in ACTIVE_SESSION_STATUSES:
        await callback.answer("Активная игра уже завершена.", show_alert=True)
        return
    group = await _managed_group_for_callback(
        callback,
        bot,
        session,
        group_id=game.group_id,
        requester_id=int(requester_raw),
    )
    if group is None:
        return
    definition = game_registry.get(game.game_type)
    title = definition.title if definition is not None else game.game_type
    await callback.message.edit_text(
        "🛑 ПРИНУДИТЕЛЬНАЯ ОТМЕНА\n\n"
        f"Отменить активную игру {title}?\n\n"
        "Сессия будет закрыта без победителя и без начисления рейтинга. Старые игровые кнопки станут неактивны.",
        reply_markup=_confirm_markup(game.id, int(requester_raw), group.id),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^gm:adm:confirm:\d+:\d+$"))
async def game_admin_cancel_confirm(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    _, _, _, game_raw, requester_raw = (callback.data or "").split(":")
    game_id = int(game_raw)
    requester_id = int(requester_raw)
    game = await manager.get_game(session, game_id=game_id)
    if game is None:
        await callback.answer("Игра уже удалена или завершена.", show_alert=True)
        return
    group = await _managed_group_for_callback(
        callback,
        bot,
        session,
        group_id=game.group_id,
        requester_id=requester_id,
    )
    if group is None:
        return
    if game.status not in ACTIVE_SESSION_STATUSES:
        await _render_admin(callback, session, group=group, requester_id=requester_id)
        await callback.answer("Игра уже завершена.", show_alert=True)
        return

    await manager.cancel_game(session, game_id=game.id, reason="admin_cancelled")
    await retire_active_messages(
        bot,
        session,
        game_id=game.id,
        replacement_text="🛑 Игра принудительно отменена управляющим группы.",
    )
    await ensure_game_panel(bot, session, group=group, pin=False)
    await _render_admin(callback, session, group=group, requester_id=requester_id)
    await callback.answer("🛑 Активная игра отменена")


@router.callback_query(F.data.regexp(r"^gm:adm:close:\d+:\d+$"))
async def game_admin_close(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    if callback.message is None:
        return
    _, _, _, group_raw, requester_raw = (callback.data or "").split(":")
    group = await _managed_group_for_callback(
        callback,
        bot,
        session,
        group_id=int(group_raw),
        requester_id=int(requester_raw),
    )
    if group is None:
        return
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        await callback.answer("Не удалось закрыть служебную карточку.", show_alert=True)
        return
    await callback.answer()
