from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GameGroupSettings, GamePlayer
from app.db.models import Group
from app.games.actions import GameActionError
from app.games.enums import GameSessionStatus
from app.games.lobby import close_lobby_message
from app.games.manager import GameManager, GamePlayerError
from app.games.mafia.actions import record_mafia_number_action, target_map_lines
from app.games.mafia.game import MafiaGame
from app.games.mafia.presentation import mafia_public_text, mafia_results_text, sync_mafia_ui
from app.services.access import can_manage_group


router = Router(name=__name__)
manager = GameManager()
engine = MafiaGame()

ROLE_LABELS = {
    "civilian": "👨 Мирный житель",
    "mafia": "🔪 Мафия",
    "doctor": "🩺 Доктор",
    "commissioner": "🕵️ Комиссар",
}


async def _game_group(callback: CallbackQuery, session: AsyncSession, game_id: int):
    if callback.message is None:
        await callback.answer("Игровое сообщение недоступно.", show_alert=True)
        return None
    game = await manager.get_game(session, game_id=game_id)
    if game is None or game.game_type != "mafia":
        await callback.answer("❌ Эта кнопка больше не активна.", show_alert=True)
        return None
    group = await session.get(Group, game.group_id)
    if group is None or not group.is_active or callback.message.chat.id != group.telegram_chat_id:
        await callback.answer("❌ Эта кнопка относится к другой игровой сессии.", show_alert=True)
        return None
    return game, group


async def _running_mafia(
    callback: CallbackQuery,
    session: AsyncSession,
    game_id: int,
    phase_seq: int,
):
    resolved = await _game_group(callback, session, game_id)
    if resolved is None:
        return None
    game, _ = resolved
    if game.status != GameSessionStatus.RUNNING.value:
        await callback.answer("❌ Эта кнопка больше не активна.", show_alert=True)
        return None
    if game.phase_seq != phase_seq:
        await callback.answer("⏳ Эта кнопка относится к прошлой фазе.", show_alert=True)
        return None
    return game


async def _player(session: AsyncSession, game_id: int, user_id: int) -> GamePlayer | None:
    return await session.scalar(
        select(GamePlayer).where(
            GamePlayer.game_id == game_id,
            GamePlayer.user_telegram_id == user_id,
        )
    )


async def _can_control(bot: Bot, session: AsyncSession, group: Group, game, user_id: int) -> bool:
    if user_id == game.creator_telegram_id:
        return True
    return await can_manage_group(bot, group, user_id, session)


async def _commissioner_result(session: AsyncSession, game_id: int, target_user_id: int | None) -> str:
    if target_user_id is None:
        return "🔎 Результат проверки недоступен."
    target = await _player(session, game_id, target_user_id)
    return (
        "🔎 Результат: игрок относится к Мафии."
        if target is not None and target.team == "mafia"
        else "🔎 Результат: игрок не относится к Мафии."
    )


@router.callback_query(F.data == "gm:rules:mafia")
async def mafia_rules(callback: CallbackQuery) -> None:
    await callback.answer(
        "🐺 Мафия: днём обсуждайте и голосуйте кнопками. Ночью Мафия выбирает жертву, Доктор лечит, Комиссар проверяет. Победа мирных — вся мафия устранена; победа мафии — мафии не меньше, чем остальных живых.",
        show_alert=True,
    )


@router.callback_query(F.data.regexp(r"^gm:ms:\d+$"))
async def mafia_start(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    game_id = int((callback.data or "").rsplit(":", 1)[-1])
    resolved = await _game_group(callback, session, game_id)
    if resolved is None:
        return
    game, group = resolved
    if game.status != GameSessionStatus.LOBBY.value:
        await callback.answer("❌ Это лобби уже закрыто.", show_alert=True)
        return
    settings = await session.get(GameGroupSettings, group.id)
    can_start = await _can_control(bot, session, group, game, callback.from_user.id)
    if not can_start and settings is not None and settings.creator_policy == "any_at_min":
        player = await _player(session, game.id, callback.from_user.id)
        can_start = player is not None and player.status == "joined"
    if not can_start:
        await callback.answer("❌ У вас нет права запускать это лобби.", show_alert=True)
        return
    try:
        game = await manager.start_lobby(session, game_id=game.id)
        await engine.start(session, game)
    except GamePlayerError:
        await callback.answer("Для старта Мафии нужно минимум 4 игрока.", show_alert=True)
        return
    except Exception:
        locked = await manager.get_game(session, game_id=game.id, for_update=True)
        if locked is not None and locked.status == GameSessionStatus.RUNNING.value:
            locked.status = GameSessionStatus.RECOVERING.value
            locked.phase = "recovering"
            await session.commit()
        await callback.answer("Игра сохранена для восстановления после ошибки запуска.", show_alert=True)
        return
    await close_lobby_message(bot, session, group=group, game=game, text="▶️ 🐺 Мафия началась.")
    latest = await manager.get_game(session, game_id=game.id)
    if latest is not None:
        await sync_mafia_ui(bot, session, latest)
    await callback.answer("▶️ Мафия началась")


@router.callback_query(F.data.regexp(r"^gm:mr:\d+:\d+$"))
async def mafia_private_role(callback: CallbackQuery, session: AsyncSession) -> None:
    _, _, game_raw, phase_raw = (callback.data or "").split(":")
    game = await _running_mafia(callback, session, int(game_raw), int(phase_raw))
    if game is None:
        return
    player = await _player(session, game.id, callback.from_user.id)
    if player is None:
        await callback.answer("❌ Вы не участвуете в этой игре.", show_alert=True)
        return
    role = ROLE_LABELS.get(player.role or "", "Неизвестная роль")
    text = f"Ваша роль: {role}."
    if player.role == "mafia":
        teammates = list((await session.scalars(
            select(GamePlayer).where(
                GamePlayer.game_id == game.id,
                GamePlayer.team == "mafia",
                GamePlayer.user_telegram_id != player.user_telegram_id,
            ).order_by(GamePlayer.id)
        )).all())
        if teammates:
            text += "\nСоюзники: " + ", ".join(mate.display_name for mate in teammates) + "."
    elif player.role == "doctor":
        text += "\nНочью выберите игрока для лечения."
    elif player.role == "commissioner":
        text += "\nНочью выберите игрока для проверки."
    else:
        text += "\nДнём ищите мафию и голосуйте."
    await callback.answer(text[:200], show_alert=True)


@router.callback_query(F.data.regexp(r"^gm:mm:\d+:\d+:[12]$"))
async def mafia_private_map(callback: CallbackQuery, session: AsyncSession) -> None:
    _, _, game_raw, phase_raw, page_raw = (callback.data or "").split(":")
    game = await _running_mafia(callback, session, int(game_raw), int(phase_raw))
    if game is None:
        return
    start, end = (1, 7) if int(page_raw) == 1 else (8, 15)
    try:
        lines = await target_map_lines(
            session,
            game=game,
            actor_user_id=callback.from_user.id,
            start=start,
            end=end,
        )
    except GameActionError:
        await callback.answer("Сейчас у вас нет доступного выбора.", show_alert=True)
        return
    if not lines:
        await callback.answer("На этой странице целей нет.", show_alert=True)
        return
    await callback.answer(("Ваши номера:\n" + "\n".join(lines))[:200], show_alert=True)


@router.callback_query(F.data.regexp(r"^gm:ma:\d+:\d+:\d+$"))
async def mafia_number_action(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    _, _, game_raw, phase_raw, number_raw = (callback.data or "").split(":")
    game = await _running_mafia(callback, session, int(game_raw), int(phase_raw))
    if game is None:
        return
    player = await _player(session, game.id, callback.from_user.id)
    try:
        action, created = await record_mafia_number_action(
            session,
            game=game,
            actor_user_id=callback.from_user.id,
            number=int(number_raw),
        )
    except GameActionError as error:
        text = str(error)
        if "role has no" in text:
            text = "❌ Сейчас не ваш ход."
        elif "actor is not alive" in text:
            text = "❌ Вы не участвуете в этой фазе."
        elif "target" in text:
            text = "❌ Эта цель больше недоступна."
        else:
            text = "❌ Сейчас этот выбор недоступен."
        await callback.answer(text, show_alert=True)
        return

    response = "✅ Выбор принят: №" + number_raw if created else "✅ Ваш выбор уже принят."
    if player is not None and player.role == "commissioner":
        response = await _commissioner_result(session, game.id, action.target_telegram_id)

    if created:
        player = await _player(session, game.id, callback.from_user.id)
        if player is not None and player.afk_count:
            player.afk_count = 0
            await session.commit()
        await engine.maybe_advance_if_ready(session, game)
        latest = await manager.get_game(session, game_id=game.id)
        if latest is not None:
            await sync_mafia_ui(bot, session, latest)
    await callback.answer(response[:200], show_alert=player is not None and player.role == "commissioner")


@router.callback_query(F.data.regexp(r"^gm:mc:\d+:\d+$"))
async def mafia_cancel_running(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    _, _, game_raw, phase_raw = (callback.data or "").split(":")
    game = await _running_mafia(callback, session, int(game_raw), int(phase_raw))
    if game is None:
        return
    group = await session.get(Group, game.group_id)
    if group is None or not await _can_control(bot, session, group, game, callback.from_user.id):
        await callback.answer("❌ Отменить игру может создатель или администратор.", show_alert=True)
        return
    game = await manager.cancel_game(session, game_id=game.id, reason="cancelled_by_user")
    await sync_mafia_ui(bot, session, game)
    await callback.answer("Игра отменена")


@router.callback_query(F.data.regexp(r"^gm:mres:\d+$"))
async def mafia_results(callback: CallbackQuery, session: AsyncSession) -> None:
    game_id = int((callback.data or "").rsplit(":", 1)[-1])
    resolved = await _game_group(callback, session, game_id)
    if resolved is None or callback.message is None:
        return
    game, _ = resolved
    if game.status != GameSessionStatus.FINISHED.value:
        await callback.answer("Результаты этой партии ещё не доступны.", show_alert=True)
        return
    text = await mafia_results_text(session, game)
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ К итогу", callback_data=f"gm:mfinal:{game.id}")]
    ])
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^gm:mfinal:\d+$"))
async def mafia_final(callback: CallbackQuery, session: AsyncSession) -> None:
    game_id = int((callback.data or "").rsplit(":", 1)[-1])
    resolved = await _game_group(callback, session, game_id)
    if resolved is None or callback.message is None:
        return
    game, _ = resolved
    text = await mafia_public_text(session, game)
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Сыграть ещё", callback_data="gm:new:mafia")],
        [InlineKeyboardButton(text="📋 Результаты", callback_data=f"gm:mres:{game.id}")],
        [InlineKeyboardButton(text="🏆 Рейтинг", callback_data="gm:rating")],
    ])
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()
