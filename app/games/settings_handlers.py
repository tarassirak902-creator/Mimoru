from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GameGroupSettings
from app.db.models import Group
from app.games.registry import game_registry
from app.services.access import can_manage_group


router = Router(name=__name__)

_MAFIA_TIMER_PRESETS: dict[str, tuple[int, ...]] = {
    "day_start": (5, 10, 15, 20, 30, 60),
    "discussion": (30, 60, 90, 120, 180, 300),
    "voting": (15, 30, 60, 90, 120, 180),
    "result": (5, 10, 15, 20, 30, 60),
    "night_start": (5, 10, 15, 20, 30, 60),
    "night": (15, 30, 60, 90, 120, 180),
}
_MAFIA_TIMER_DEFAULTS: dict[str, int] = {
    "day_start": 15,
    "discussion": 90,
    "voting": 60,
    "result": 10,
    "night_start": 10,
    "night": 60,
}
_MAFIA_TIMER_SETTING_KEYS: dict[str, str] = {
    "day_start": "day_start_seconds",
    "discussion": "discussion_seconds",
    "voting": "voting_seconds",
    "result": "result_seconds",
    "night_start": "night_start_seconds",
    "night": "night_seconds",
}


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


def _game_codes() -> list[str]:
    return [definition.code for definition in game_registry.all()]


def _effective_allowed_games(settings: GameGroupSettings | None) -> set[str]:
    all_codes = set(_game_codes())
    if settings is None or not settings.allowed_games:
        return all_codes
    return {code for code in settings.allowed_games if code in all_codes}


def _mafia_dict(settings: GameGroupSettings | None) -> dict:
    all_settings = dict(settings.settings_json or {}) if settings is not None else {}
    return dict(all_settings.get("mafia") or {})


def _mafia_values(settings: GameGroupSettings | None) -> tuple[bool, bool, int]:
    mafia = _mafia_dict(settings)
    self_heal = bool(mafia.get("doctor_can_self_heal", True))
    repeat_heal = bool(mafia.get("doctor_can_heal_same_player_twice", False))
    try:
        afk_strikes = int(mafia.get("afk_strikes_to_remove", 2))
    except (TypeError, ValueError):
        afk_strikes = 2
    afk_strikes = max(1, min(5, afk_strikes))
    return self_heal, repeat_heal, afk_strikes


def _mafia_timer_values(settings: GameGroupSettings | None) -> dict[str, int]:
    mafia = _mafia_dict(settings)
    values: dict[str, int] = {}
    for timer, default in _MAFIA_TIMER_DEFAULTS.items():
        setting_key = _MAFIA_TIMER_SETTING_KEYS[timer]
        try:
            value = int(mafia.get(setting_key, default))
        except (TypeError, ValueError):
            value = default
        presets = _MAFIA_TIMER_PRESETS[timer]
        values[timer] = value if value in presets else default
    return values


def _next_mafia_timer_value(timer: str, current: int) -> int:
    presets = _MAFIA_TIMER_PRESETS[timer]
    try:
        index = presets.index(current)
    except ValueError:
        return _MAFIA_TIMER_DEFAULTS[timer]
    return presets[(index + 1) % len(presets)]


def settings_text(settings: GameGroupSettings | None) -> str:
    enabled, rating_enabled, creator_policy = _setting_values(settings)
    creator_label = (
        "создатель лобби или администратор"
        if creator_policy == "lobby_creator"
        else "любой участник лобби после набора минимума"
    )
    allowed_count = len(_effective_allowed_games(settings))
    total_count = len(_game_codes())
    return (
        "⚙️ НАСТРОЙКИ ИГР\n\n"
        f"🎮 Игры: {'включены' if enabled else 'выключены'}\n"
        f"🧩 Разрешённые игры: {allowed_count}/{total_count}\n"
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
    allowed_count = len(_effective_allowed_games(settings))
    total_count = len(_game_codes())
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🎮 Игры: {'ON' if enabled else 'OFF'}",
            callback_data="gm:cfg:enabled",
        )],
        [InlineKeyboardButton(
            text=f"🧩 Разрешённые: {allowed_count}/{total_count}",
            callback_data="gm:cfg:games",
        )],
        [InlineKeyboardButton(
            text=f"🏆 Рейтинг: {'ON' if rating_enabled else 'OFF'}",
            callback_data="gm:cfg:rating",
        )],
        [InlineKeyboardButton(text=creator_text, callback_data="gm:cfg:creator")],
        [InlineKeyboardButton(text="🐺 Мафия", callback_data="gm:cfg:mafia")],
        [InlineKeyboardButton(text="◀️ В игровой центр", callback_data="gm:home")],
    ])


def allowed_games_text(settings: GameGroupSettings | None) -> str:
    allowed = _effective_allowed_games(settings)
    definitions = game_registry.all()
    lines = [
        "🧩 РАЗРЕШЁННЫЕ ИГРЫ",
        "",
        f"Включено: {len(allowed)}/{len(definitions)}",
        "",
        "Нажмите на игру, чтобы разрешить или запретить создание новых лобби.",
        "Уже запущенная партия не останавливается.",
    ]
    return "\n".join(lines)


def allowed_games_markup(settings: GameGroupSettings | None) -> InlineKeyboardMarkup:
    allowed = _effective_allowed_games(settings)
    definitions = game_registry.all()
    buttons = [
        InlineKeyboardButton(
            text=f"{'✅' if definition.code in allowed else '❌'} {definition.title}",
            callback_data=f"gm:cfg:game:{definition.code}",
        )
        for definition in definitions
    ]
    rows = [buttons[index:index + 2] for index in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text="◀️ Общие настройки", callback_data="gm:settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def mafia_settings_text(settings: GameGroupSettings | None) -> str:
    self_heal, repeat_heal, afk_strikes = _mafia_values(settings)
    return (
        "🐺 МАФИЯ · НАСТРОЙКИ\n\n"
        f"🩺 Доктор лечит себя: {'да' if self_heal else 'нет'}\n"
        f"🔁 Доктор лечит одну цель две ночи подряд: {'да' if repeat_heal else 'нет'}\n"
        f"⌛ Удаление за AFK: после {afk_strikes} пропущенных обязательных действий\n\n"
        "Изменения применяются к следующей партии Mafia. "
        "Правила уже запущенной партии не меняются."
    )


def mafia_settings_markup(settings: GameGroupSettings | None) -> InlineKeyboardMarkup:
    self_heal, repeat_heal, afk_strikes = _mafia_values(settings)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🩺 Самолечение: {'ON' if self_heal else 'OFF'}",
            callback_data="gm:cfg:mafia:self",
        )],
        [InlineKeyboardButton(
            text=f"🔁 Та же цель подряд: {'ON' if repeat_heal else 'OFF'}",
            callback_data="gm:cfg:mafia:repeat",
        )],
        [InlineKeyboardButton(
            text=f"⌛ AFK до удаления: {afk_strikes}",
            callback_data="gm:cfg:mafia:afk",
        )],
        [InlineKeyboardButton(text="⏱ Таймеры", callback_data="gm:cfg:mafia:timers")],
        [InlineKeyboardButton(text="♻️ Сбросить настройки", callback_data="gm:cfg:mafia:reset")],
        [InlineKeyboardButton(text="◀️ Общие настройки", callback_data="gm:settings")],
    ])


def mafia_reset_text() -> str:
    return (
        "♻️ СБРОС НАСТРОЕК MAFIA\n\n"
        "Будут восстановлены стандартные правила Доктора, AFK-порог и все таймеры Mafia.\n\n"
        "Общие настройки игр, рейтинг и другие параметры группы не изменятся. "
        "Сброс применится только к следующим партиям."
    )


def mafia_reset_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="♻️ Сбросить", callback_data="gm:cfg:mafia:reset:confirm")],
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="gm:cfg:mafia")],
    ])


def mafia_timer_settings_text(settings: GameGroupSettings | None) -> str:
    timers = _mafia_timer_values(settings)
    return (
        "🐺 МАФИЯ · ТАЙМЕРЫ\n\n"
        f"🌅 Старт дня: {timers['day_start']} с\n"
        f"💬 Обсуждение: {timers['discussion']} с\n"
        f"🗳 Голосование: {timers['voting']} с\n"
        f"📣 Показ результата: {timers['result']} с\n"
        f"🌙 Старт ночи: {timers['night_start']} с\n"
        f"🎯 Ночные действия: {timers['night']} с\n\n"
        "Нажатие на кнопку переключает следующий безопасный пресет. "
        "Изменения применяются со следующей партии."
    )


def mafia_timer_settings_markup(settings: GameGroupSettings | None) -> InlineKeyboardMarkup:
    timers = _mafia_timer_values(settings)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"🌅 День: {timers['day_start']}с",
                callback_data="gm:cfg:mafia:timer:day_start",
            ),
            InlineKeyboardButton(
                text=f"💬 Обсуждение: {timers['discussion']}с",
                callback_data="gm:cfg:mafia:timer:discussion",
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"🗳 Голосование: {timers['voting']}с",
                callback_data="gm:cfg:mafia:timer:voting",
            ),
            InlineKeyboardButton(
                text=f"📣 Результат: {timers['result']}с",
                callback_data="gm:cfg:mafia:timer:result",
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"🌙 Старт ночи: {timers['night_start']}с",
                callback_data="gm:cfg:mafia:timer:night_start",
            ),
            InlineKeyboardButton(
                text=f"🎯 Ночь: {timers['night']}с",
                callback_data="gm:cfg:mafia:timer:night",
            ),
        ],
        [InlineKeyboardButton(text="◀️ Настройки Mafia", callback_data="gm:cfg:mafia")],
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


async def _locked_settings(
    session: AsyncSession,
    *,
    group_id: int,
) -> GameGroupSettings | None:
    locked_group = await session.scalar(
        select(Group)
        .where(Group.id == group_id, Group.is_active.is_(True))
        .with_for_update()
    )
    if locked_group is None:
        return None
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
    return settings


async def _render(callback: CallbackQuery, settings: GameGroupSettings | None) -> None:
    if callback.message is None:
        return
    await callback.message.edit_text(
        settings_text(settings),
        reply_markup=settings_markup(settings),
    )


async def _render_allowed_games(callback: CallbackQuery, settings: GameGroupSettings | None) -> None:
    if callback.message is None:
        return
    await callback.message.edit_text(
        allowed_games_text(settings),
        reply_markup=allowed_games_markup(settings),
    )


async def _render_mafia(callback: CallbackQuery, settings: GameGroupSettings | None) -> None:
    if callback.message is None:
        return
    await callback.message.edit_text(
        mafia_settings_text(settings),
        reply_markup=mafia_settings_markup(settings),
    )


async def _render_mafia_timers(callback: CallbackQuery, settings: GameGroupSettings | None) -> None:
    if callback.message is None:
        return
    await callback.message.edit_text(
        mafia_timer_settings_text(settings),
        reply_markup=mafia_timer_settings_markup(settings),
    )


@router.callback_query(F.data == "gm:settings")
async def game_settings(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    group = await _managed_group(callback, bot, session)
    if group is None:
        return
    settings = await session.get(GameGroupSettings, group.id)
    await _render(callback, settings)
    await callback.answer()


@router.callback_query(F.data == "gm:cfg:games")
async def allowed_games_settings(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    group = await _managed_group(callback, bot, session)
    if group is None:
        return
    settings = await session.get(GameGroupSettings, group.id)
    await _render_allowed_games(callback, settings)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^gm:cfg:game:[a-z0-9_]{1,32}$"))
async def allowed_game_toggle(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    group = await _managed_group(callback, bot, session)
    if group is None:
        return
    code = (callback.data or "").rsplit(":", 1)[-1]
    if game_registry.get(code) is None:
        await callback.answer("Эта игра больше не доступна.", show_alert=True)
        return
    settings = await _locked_settings(session, group_id=group.id)
    if settings is None:
        await callback.answer("Группа больше не подключена к Mimoru.", show_alert=True)
        return

    all_codes = _game_codes()
    allowed = _effective_allowed_games(settings)
    if code in allowed:
        if len(allowed) <= 1:
            await callback.answer(
                "Нельзя отключить последнюю разрешённую игру. Используйте общий переключатель «Игры: OFF».",
                show_alert=True,
            )
            return
        allowed.remove(code)
    else:
        allowed.add(code)

    settings.allowed_games = [] if allowed == set(all_codes) else [item for item in all_codes if item in allowed]
    await session.commit()
    await session.refresh(settings)
    await _render_allowed_games(callback, settings)
    await callback.answer("Список разрешённых игр сохранён")


@router.callback_query(F.data == "gm:cfg:mafia")
async def mafia_settings(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    group = await _managed_group(callback, bot, session)
    if group is None:
        return
    settings = await session.get(GameGroupSettings, group.id)
    await _render_mafia(callback, settings)
    await callback.answer()


@router.callback_query(F.data == "gm:cfg:mafia:timers")
async def mafia_timer_settings(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    group = await _managed_group(callback, bot, session)
    if group is None:
        return
    settings = await session.get(GameGroupSettings, group.id)
    await _render_mafia_timers(callback, settings)
    await callback.answer()


@router.callback_query(F.data == "gm:cfg:mafia:reset")
async def mafia_settings_reset_prompt(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    group = await _managed_group(callback, bot, session)
    if group is None:
        return
    if callback.message is not None:
        await callback.message.edit_text(mafia_reset_text(), reply_markup=mafia_reset_markup())
    await callback.answer()


@router.callback_query(F.data.regexp(r"^gm:cfg:(enabled|rating|creator)$"))
async def game_settings_toggle(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    group = await _managed_group(callback, bot, session)
    if group is None:
        return
    settings = await _locked_settings(session, group_id=group.id)
    if settings is None:
        await callback.answer("Группа больше не подключена к Mimoru.", show_alert=True)
        return

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


@router.callback_query(F.data.regexp(r"^gm:cfg:mafia:(self|repeat|afk)$"))
async def mafia_settings_toggle(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    group = await _managed_group(callback, bot, session)
    if group is None:
        return
    settings = await _locked_settings(session, group_id=group.id)
    if settings is None:
        await callback.answer("Группа больше не подключена к Mimoru.", show_alert=True)
        return

    all_settings = dict(settings.settings_json or {})
    mafia = dict(all_settings.get("mafia") or {})
    self_heal, repeat_heal, afk_strikes = _mafia_values(settings)
    action = (callback.data or "").rsplit(":", 1)[-1]
    if action == "self":
        mafia["doctor_can_self_heal"] = not self_heal
    elif action == "repeat":
        mafia["doctor_can_heal_same_player_twice"] = not repeat_heal
    else:
        mafia["afk_strikes_to_remove"] = 1 if afk_strikes >= 5 else afk_strikes + 1
    all_settings["mafia"] = mafia
    settings.settings_json = all_settings

    await session.commit()
    await session.refresh(settings)
    await _render_mafia(callback, settings)
    await callback.answer("Настройки Mafia сохранены")


@router.callback_query(
    F.data.regexp(r"^gm:cfg:mafia:timer:(day_start|discussion|voting|result|night_start|night)$")
)
async def mafia_timer_settings_toggle(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
) -> None:
    group = await _managed_group(callback, bot, session)
    if group is None:
        return
    settings = await _locked_settings(session, group_id=group.id)
    if settings is None:
        await callback.answer("Группа больше не подключена к Mimoru.", show_alert=True)
        return

    timer = (callback.data or "").rsplit(":", 1)[-1]
    timers = _mafia_timer_values(settings)
    all_settings = dict(settings.settings_json or {})
    mafia = dict(all_settings.get("mafia") or {})
    mafia[_MAFIA_TIMER_SETTING_KEYS[timer]] = _next_mafia_timer_value(timer, timers[timer])
    all_settings["mafia"] = mafia
    settings.settings_json = all_settings

    await session.commit()
    await session.refresh(settings)
    await _render_mafia_timers(callback, settings)
    await callback.answer("Таймер Mafia сохранён")


@router.callback_query(F.data == "gm:cfg:mafia:reset:confirm")
async def mafia_settings_reset_confirm(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
) -> None:
    group = await _managed_group(callback, bot, session)
    if group is None:
        return
    settings = await _locked_settings(session, group_id=group.id)
    if settings is None:
        await callback.answer("Группа больше не подключена к Mimoru.", show_alert=True)
        return

    all_settings = dict(settings.settings_json or {})
    all_settings.pop("mafia", None)
    settings.settings_json = all_settings
    await session.commit()
    await session.refresh(settings)
    await _render_mafia(callback, settings)
    await callback.answer("Настройки Mafia сброшены")