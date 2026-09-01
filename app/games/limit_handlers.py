from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GameGroupSettings
from app.db.models import Group
from app.games.group_limits import PLAYER_CAP_PRESETS, configured_player_cap, set_player_cap
from app.services.access import can_manage_group


router = Router(name=__name__)
GROUP_TYPES = {"group", "supergroup"}


async def _active_group(session: AsyncSession, chat_id: int) -> Group | None:
    return await session.scalar(
        select(Group).where(
            Group.telegram_chat_id == chat_id,
            Group.is_active.is_(True),
        )
    )


def _text(settings: GameGroupSettings | None) -> str:
    cap = configured_player_cap(settings)
    current = "без общего ограничения" if cap is None else f"до {cap} игроков"
    return (
        "👥 ЛИМИТ ИГРОКОВ\n\n"
        f"Текущий лимит: {current}.\n\n"
        "Лимит ограничивает новые игровые лобби группы, но не увеличивает собственный максимум игры. "
        "Уже созданное лобби сохраняет лимит, с которым оно было открыто.\n\n"
        "Выберите новый лимит кнопкой ниже."
    )


def _markup(group_id: int, requester_id: int, settings: GameGroupSettings | None) -> InlineKeyboardMarkup:
    current = configured_player_cap(settings)

    def button(value: int) -> InlineKeyboardButton:
        marker = "✓ " if current == value else ""
        return InlineKeyboardButton(
            text=f"{marker}{value}",
            callback_data=f"gm:cap:{group_id}:{requester_id}:{value}",
        )

    preset_buttons = [button(value) for value in PLAYER_CAP_PRESETS]
    rows = [preset_buttons[index:index + 3] for index in range(0, len(preset_buttons), 3)]
    default_marker = "✓ " if current is None else ""
    rows.append([
        InlineKeyboardButton(
            text=f"{default_marker}♾ Без ограничения",
            callback_data=f"gm:cap:{group_id}:{requester_id}:0",
        )
    ])
    rows.append([
        InlineKeyboardButton(
            text="❌ Закрыть",
            callback_data=f"gm:capclose:{group_id}:{requester_id}",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _locked_settings(session: AsyncSession, group_id: int) -> GameGroupSettings | None:
    group = await session.scalar(
        select(Group).where(Group.id == group_id, Group.is_active.is_(True)).with_for_update()
    )
    if group is None:
        return None
    settings = await session.get(GameGroupSettings, group.id)
    if settings is None:
        settings = GameGroupSettings(
            group_id=group.id,
            enabled=True,
            allowed_games=[],
            creator_policy="lobby_creator",
            allow_duels=False,
            rating_enabled=True,
            settings_json={},
        )
        session.add(settings)
        await session.flush()
    return settings


async def _callback_group(
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
        await callback.answer("Эта карточка открыта другим управляющим.", show_alert=True)
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
        await callback.answer("❌ Настройка доступна только управляющим группы.", show_alert=True)
        return None
    return group


@router.message(Command("game_limit"), F.chat.type.in_(GROUP_TYPES))
async def game_limit_command(message: Message, bot: Bot, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    group = await _active_group(session, message.chat.id)
    if group is None:
        return
    if not await can_manage_group(bot, group, message.from_user.id, session):
        await message.answer("❌ Настройка лимита игр доступна только управляющим группы.")
        return
    settings = await session.get(GameGroupSettings, group.id)
    await message.answer(
        _text(settings),
        reply_markup=_markup(group.id, message.from_user.id, settings),
    )


@router.callback_query(F.data.regexp(r"^gm:cap:\d+:\d+:(0|4|6|8|12|20)$"))
async def game_limit_set(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    _, _, group_raw, requester_raw, value_raw = (callback.data or "").split(":")
    group_id = int(group_raw)
    requester_id = int(requester_raw)
    group = await _callback_group(
        callback,
        bot,
        session,
        group_id=group_id,
        requester_id=requester_id,
    )
    if group is None or callback.message is None:
        return
    settings = await _locked_settings(session, group.id)
    if settings is None:
        await callback.answer("Группа больше не активна.", show_alert=True)
        return
    value = int(value_raw)
    set_player_cap(settings, None if value == 0 else value)
    await session.commit()
    await session.refresh(settings)
    try:
        await callback.message.edit_text(
            _text(settings),
            reply_markup=_markup(group.id, requester_id, settings),
        )
    except TelegramBadRequest as error:
        if "message is not modified" not in str(error).casefold():
            raise
    await callback.answer("👥 Лимит сохранён")


@router.callback_query(F.data.regexp(r"^gm:capclose:\d+:\d+$"))
async def game_limit_close(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    _, _, group_raw, requester_raw = (callback.data or "").split(":")
    group = await _callback_group(
        callback,
        bot,
        session,
        group_id=int(group_raw),
        requester_id=int(requester_raw),
    )
    if group is None or callback.message is None:
        return
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        await callback.answer("Не удалось закрыть карточку.", show_alert=True)
        return
    await callback.answer()
