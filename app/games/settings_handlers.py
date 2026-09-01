from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GameGroupSettings
from app.db.models import Group
from app.services.access import can_manage_group


router = Router(name=__name__)


async def _active_group(session: AsyncSession, chat_id: int) -> Group | None:
    return await session.scalar(
        select(Group).where(
            Group.telegram_chat_id == chat_id,
            Group.is_active.is_(True),
        )
    )


def _setting_values(settings: GameGroupSettings | None) -> tuple[bool, bool, str]:
    if settings is None:
        return True, True, "lobby_creator"
    return settings.enabled, settings.rating_enabled, settings.creator_policy


def settings_text(settings: GameGroupSettings | None) -> str:
    enabled, rating_enabled, creator_policy = _setting_values(settings)
    creator_label = (
        "создатель лобби или администратор"
        if creator_policy == "lobby_creator"
        else "любой участник лобби после набора минимума"
    )
    return (
        "⚙️ НАСТРОЙКИ ИГР\n\n"
        f"🎮 Игры: {'включены' if enabled else 'выключены'}\n"
        f"🏆 Рейтинг: {'включён' if rating_enabled else 'выключен'}\n"
        f"▶️ Запуск лобби: {creator_label}\n\n"
        "Изменять эти параметры могут только управляющие группы. "
        "Отключение игр не останавливает уже запущенную партию."
    )


def settings_markup(settings: GameGroupSettings | None) -> InlineKeyboardMarkup:
    enabled, rating_enabled, creator_policy = _setting_values(settings)
    creator_text = (
        "👤 Запуск: создатель"
        if creator_policy == "lobby_creator"
        else "👥 Запуск: участники"
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🎮 Игры: {'ON' if enabled else 'OFF'}",
            callback_data="gm:cfg:enabled",
        )],
        [InlineKeyboardButton(
            text=f"🏆 Рейтинг: {'ON' if rating_enabled else 'OFF'}",
            callback_data="gm:cfg:rating",
        )],
        [InlineKeyboardButton(text=creator_text, callback_data="gm:cfg:creator")],
        [InlineKeyboardButton(text="◀️ В игровой центр", callback_data="gm:home")],
    ])


async def _managed_group(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
) -> Group | None:
    if callback.message is None:
        await callback.answer("Игровая панель недоступна.", show_alert=True)
        return None
    group = await _active_group(session, callback.message.chat.id)
    if group is None:
        await callback.answer("Группа больше не подключена к Mimoru.", show_alert=True)
        return None
    if not await can_manage_group(bot, group, callback.from_user.id, session):
        await callback.answer("❌ Настройки игр доступны только управляющим группы.", show_alert=True)
        return None
    return group


async def _render(callback: CallbackQuery, settings: GameGroupSettings | None) -> None:
    if callback.message is None:
        return
    await callback.message.edit_text(
        settings_text(settings),
        reply_markup=settings_markup(settings),
    )


@router.callback_query(F.data == "gm:settings")
async def game_settings(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    group = await _managed_group(callback, bot, session)
    if group is None:
        return
    settings = await session.get(GameGroupSettings, group.id)
    await _render(callback, settings)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^gm:cfg:(enabled|rating|creator)$"))
async def game_settings_toggle(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    group = await _managed_group(callback, bot, session)
    if group is None:
        return

    locked_group = await session.scalar(
        select(Group)
        .where(Group.id == group.id, Group.is_active.is_(True))
        .with_for_update()
    )
    if locked_group is None:
        await callback.answer("Группа больше не подключена к Mimoru.", show_alert=True)
        return

    settings = await session.get(GameGroupSettings, locked_group.id)
    if settings is None:
        settings = GameGroupSettings(
            group_id=locked_group.id,
            enabled=True,
            allowed_games=[],
            creator_policy="lobby_creator",
            allow_duels=False,
            rating_enabled=True,
            settings_json={},
        )
        session.add(settings)
        await session.flush()

    action = (callback.data or "").rsplit(":", 1)[-1]
    if action == "enabled":
        settings.enabled = not settings.enabled
    elif action == "rating":
        settings.rating_enabled = not settings.rating_enabled
    else:
        settings.creator_policy = (
            "any_at_min" if settings.creator_policy == "lobby_creator" else "lobby_creator"
        )

    await session.commit()
    await session.refresh(settings)
    await _render(callback, settings)
    await callback.answer("Настройки сохранены")
