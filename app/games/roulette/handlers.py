from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GameGroupSettings, GamePlayer
from app.db.models import Group
from app.games.enums import GameSessionStatus
from app.games.lobby import close_lobby_message
from app.games.manager import GameManager, GamePlayerError
from app.games.roulette.game import RouletteGame, RoulettePhase
from app.games.roulette.keyboards import roulette_finished_keyboard
from app.games.roulette.presentation import roulette_public_text, roulette_results_text, sync_roulette_ui
from app.services.access import can_manage_group


router = Router(name=__name__)
manager = GameManager()
engine = RouletteGame()


async def _game_group(callback: CallbackQuery, session: AsyncSession, game_id: int):
    if callback.message is None:
        await callback.answer("Игровое сообщение недоступно.", show_alert=True)
        return None
    game = await manager.get_game(session, game_id=game_id)
    if game is None or game.game_type != "roulette":
        await callback.answer("❌ Эта кнопка больше не активна.", show_alert=True)
        return None
    group = await session.get(Group, game.group_id)
    if group is None or not group.is_active or callback.message.chat.id != group.telegram_chat_id:
        await callback.answer("❌ Эта кнопка относится к другой игровой сессии.", show_alert=True)
        return None
    return game, group


async def _running(callback: CallbackQuery, session: AsyncSession, game_id: int, phase_seq: int):
    resolved = await _game_group(callback, session, game_id)
    if resolved is None:
        return None
    game, _ = resolved
    if game.status != GameSessionStatus.RUNNING.value or game.phase != RoulettePhase.TURN.value:
        await callback.answer("❌ Эта кнопка больше не активна.", show_alert=True)
        return None
    if game.phase_seq != phase_seq:
        await callback.answer("⏳ Эта кнопка относится к прошлому ходу.", show_alert=True)
        return None
    return game


async def _player(session: AsyncSession, game_id: int, user_id: int) -> GamePlayer | None:
    return await session.scalar(
        select(GamePlayer).where(
            GamePlayer.game_id == game_id,
            GamePlayer.user_telegram_id == user_id,
        )
    )


async def _can_start(bot: Bot, session: AsyncSession, group: Group, game, user_id: int) -> bool:
    if user_id == game.creator_telegram_id:
        return True
    if await can_manage_group(bot, group, user_id, session):
        return True
    settings = await session.get(GameGroupSettings, group.id)
    if settings is not None and settings.creator_policy == "any_at_min":
        player = await _player(session, game.id, user_id)
        return player is not None and player.status == "joined"
    return False


@router.callback_query(F.data == "gm:rules:roulette")
async def roulette_rules(callback: CallbackQuery) -> None:
    await callback.answer(
        "💣 Рулетка: в барабане 6 камер и один патрон. Игроки по очереди нажимают спуск. "
        "Пустая камера передаёт ход следующему, выстрел выбивает игрока и барабан заряжается заново. "
        "Побеждает последний оставшийся игрок.",
        show_alert=True,
    )


@router.callback_query(F.data.regexp(r"^gm:rs:\d+$"))
async def roulette_start(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    game_id = int((callback.data or "").rsplit(":", 1)[-1])
    resolved = await _game_group(callback, session, game_id)
    if resolved is None:
        return
    game, group = resolved
    if game.status != GameSessionStatus.LOBBY.value:
        await callback.answer("❌ Это лобби уже закрыто.", show_alert=True)
        return
    if not await _can_start(bot, session, group, game, callback.from_user.id):
        await callback.answer("❌ У вас нет права запускать это лобби.", show_alert=True)
        return
    try:
        game = await manager.start_lobby(session, game_id=game.id)
        await engine.start(session, game)
    except GamePlayerError:
        await callback.answer("Для Рулетки нужно минимум 2 игрока.", show_alert=True)
        return
    except Exception:
        locked = await manager.get_game(session, game_id=game.id, for_update=True)
        if locked is not None and locked.status == GameSessionStatus.RUNNING.value:
            locked.status = GameSessionStatus.RECOVERING.value
            locked.phase = "recovering"
            await session.commit()
        await callback.answer("Игра сохранена для восстановления после ошибки запуска.", show_alert=True)
        return
    await close_lobby_message(bot, session, group=group, game=game, text="▶️ 💣 Рулетка началась.")
    latest = await manager.get_game(session, game_id=game.id)
    if latest is not None:
        await sync_roulette_ui(bot, session, latest)
    await callback.answer("▶️ Рулетка началась")


@router.callback_query(F.data.regexp(r"^gm:rt:\d+:\d+$"))
async def roulette_trigger(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    _, _, game_raw, phase_raw = (callback.data or "").split(":")
    game = await _running(callback, session, int(game_raw), int(phase_raw))
    if game is None:
        return
    player = await _player(session, game.id, callback.from_user.id)
    if player is None or player.status != "alive":
        await callback.answer("❌ Вы не участвуете в этом ходе.", show_alert=True)
        return
    try:
        result, created = await engine.trigger(
            session,
            game,
            actor_telegram_id=callback.from_user.id,
        )
    except PermissionError:
        await callback.answer("❌ Сейчас не ваш ход.", show_alert=True)
        return
    except ValueError:
        await callback.answer("❌ Этот ход больше недоступен.", show_alert=True)
        return
    latest = await manager.get_game(session, game_id=game.id)
    if latest is not None:
        await sync_roulette_ui(bot, session, latest)
    if not created:
        await callback.answer("✅ Этот ход уже принят.", show_alert=True)
    elif result == "fired":
        await callback.answer("💥 Выстрел! Вы выбываете.", show_alert=True)
    else:
        await callback.answer("😮‍💨 Пусто. Вы остались в игре.", show_alert=True)


@router.callback_query(F.data.regexp(r"^gm:rc:\d+:\d+$"))
async def roulette_cancel(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    _, _, game_raw, phase_raw = (callback.data or "").split(":")
    game = await _running(callback, session, int(game_raw), int(phase_raw))
    if game is None:
        return
    group = await session.get(Group, game.group_id)
    if group is None:
        return
    if callback.from_user.id != game.creator_telegram_id and not await can_manage_group(
        bot, group, callback.from_user.id, session
    ):
        await callback.answer("❌ Отменить игру может создатель или администратор.", show_alert=True)
        return
    game = await manager.cancel_game(session, game_id=game.id, reason="cancelled_by_user")
    await sync_roulette_ui(bot, session, game)
    await callback.answer("Игра отменена")


@router.callback_query(F.data.regexp(r"^gm:rres:\d+$"))
async def roulette_results(callback: CallbackQuery, session: AsyncSession) -> None:
    game_id = int((callback.data or "").rsplit(":", 1)[-1])
    resolved = await _game_group(callback, session, game_id)
    if resolved is None or callback.message is None:
        return
    game, _ = resolved
    if game.status != GameSessionStatus.FINISHED.value:
        await callback.answer("Результаты будут доступны после завершения игры.", show_alert=True)
        return
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ К итогу", callback_data=f"gm:rfinal:{game.id}")]
        ]
    )
    await callback.message.edit_text(await roulette_results_text(session, game), reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^gm:rfinal:\d+$"))
async def roulette_final(callback: CallbackQuery, session: AsyncSession) -> None:
    game_id = int((callback.data or "").rsplit(":", 1)[-1])
    resolved = await _game_group(callback, session, game_id)
    if resolved is None or callback.message is None:
        return
    game, _ = resolved
    await callback.message.edit_text(
        await roulette_public_text(session, game),
        reply_markup=roulette_finished_keyboard(game.id),
    )
    await callback.answer()
