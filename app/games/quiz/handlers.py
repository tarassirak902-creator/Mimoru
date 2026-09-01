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
from app.games.quiz.game import QuizGame, QuizPhase
from app.games.quiz.keyboards import quiz_finished_keyboard
from app.games.quiz.presentation import quiz_public_text, quiz_results_text, sync_quiz_ui
from app.services.access import can_manage_group


router = Router(name=__name__)
manager = GameManager()
engine = QuizGame()


async def _game_group(callback: CallbackQuery, session: AsyncSession, game_id: int):
    if callback.message is None:
        await callback.answer("Игровое сообщение недоступно.", show_alert=True)
        return None
    game = await manager.get_game(session, game_id=game_id)
    if game is None or game.game_type != "quiz":
        await callback.answer("❌ Эта кнопка больше не активна.", show_alert=True)
        return None
    group = await session.get(Group, game.group_id)
    if group is None or not group.is_active or callback.message.chat.id != group.telegram_chat_id:
        await callback.answer("❌ Эта кнопка относится к другой игровой сессии.", show_alert=True)
        return None
    return game, group


async def _running_quiz(callback: CallbackQuery, session: AsyncSession, game_id: int, phase_seq: int):
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
    return await session.scalar(select(GamePlayer).where(
        GamePlayer.game_id == game_id,
        GamePlayer.user_telegram_id == user_id,
    ))


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


async def _can_control(bot: Bot, session: AsyncSession, group: Group, game, user_id: int) -> bool:
    return user_id == game.creator_telegram_id or await can_manage_group(bot, group, user_id, session)


@router.callback_query(F.data == "gm:rules:quiz")
async def quiz_rules(callback: CallbackQuery) -> None:
    await callback.answer(
        "🧠 Квиз: отвечайте на вопросы кнопками A–D. На каждый вопрос даётся ограниченное время. "
        "За правильный ответ начисляется 1 очко. После последнего вопроса побеждает лучший результат; ничья допускается.",
        show_alert=True,
    )


@router.callback_query(F.data.regexp(r"^gm:qs:\d+$"))
async def quiz_start(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
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
        await callback.answer("Для старта Квиза нужно минимум 2 игрока.", show_alert=True)
        return
    except Exception:
        locked = await manager.get_game(session, game_id=game.id, for_update=True)
        if locked is not None and locked.status == GameSessionStatus.RUNNING.value:
            locked.status = GameSessionStatus.RECOVERING.value
            locked.phase = "recovering"
            await session.commit()
        await callback.answer("Игра сохранена для восстановления после ошибки запуска.", show_alert=True)
        return
    await close_lobby_message(bot, session, group=group, game=game, text="▶️ 🧠 Квиз начался.")
    latest = await manager.get_game(session, game_id=game.id)
    if latest is not None:
        await sync_quiz_ui(bot, session, latest)
    await callback.answer("▶️ Квиз начался")


@router.callback_query(F.data.regexp(r"^gm:qa:\d+:\d+:\d+$"))
async def quiz_answer(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    _, _, game_raw, phase_raw, number_raw = (callback.data or "").split(":")
    game = await _running_quiz(callback, session, int(game_raw), int(phase_raw))
    if game is None:
        return
    if game.phase != QuizPhase.QUESTION.value:
        await callback.answer("❌ Этот вопрос уже завершён.", show_alert=True)
        return
    try:
        correct, created = await engine.answer(
            session,
            game,
            actor_telegram_id=callback.from_user.id,
            number=int(number_raw),
        )
    except PermissionError:
        await callback.answer("❌ Вы не участвуете в этом Квизе.", show_alert=True)
        return
    except ValueError:
        await callback.answer("❌ Этот ответ больше недоступен.", show_alert=True)
        return
    if not created:
        await callback.answer("✅ Ваш ответ уже принят.", show_alert=True)
        return
    latest = await manager.get_game(session, game_id=game.id)
    if latest is not None:
        await engine.maybe_advance_if_ready(session, latest)
        latest = await manager.get_game(session, game_id=game.id)
        if latest is not None:
            await sync_quiz_ui(bot, session, latest)
    await callback.answer("✅ Верно! +1 очко" if correct else "❌ Неверно. Ответ принят.", show_alert=True)


@router.callback_query(F.data.regexp(r"^gm:qc:\d+:\d+$"))
async def quiz_cancel_running(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    _, _, game_raw, phase_raw = (callback.data or "").split(":")
    game = await _running_quiz(callback, session, int(game_raw), int(phase_raw))
    if game is None:
        return
    group = await session.get(Group, game.group_id)
    if group is None or not await _can_control(bot, session, group, game, callback.from_user.id):
        await callback.answer("❌ Отменить игру может создатель или администратор.", show_alert=True)
        return
    game = await manager.cancel_game(session, game_id=game.id, reason="cancelled_by_user")
    await sync_quiz_ui(bot, session, game)
    await callback.answer("Игра отменена")


@router.callback_query(F.data.regexp(r"^gm:qres:\d+$"))
async def quiz_results(callback: CallbackQuery, session: AsyncSession) -> None:
    game_id = int((callback.data or "").rsplit(":", 1)[-1])
    resolved = await _game_group(callback, session, game_id)
    if resolved is None or callback.message is None:
        return
    game, _ = resolved
    if game.status != GameSessionStatus.FINISHED.value:
        await callback.answer("Результаты будут доступны после завершения игры.", show_alert=True)
        return
    text = await quiz_results_text(session, game)
    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ К итогу", callback_data=f"gm:qfinal:{game.id}")
    ]])
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^gm:qfinal:\d+$"))
async def quiz_final(callback: CallbackQuery, session: AsyncSession) -> None:
    game_id = int((callback.data or "").rsplit(":", 1)[-1])
    resolved = await _game_group(callback, session, game_id)
    if resolved is None or callback.message is None:
        return
    game, _ = resolved
    text = await quiz_public_text(session, game)
    await callback.message.edit_text(text, reply_markup=quiz_finished_keyboard(game.id))
    await callback.answer()
