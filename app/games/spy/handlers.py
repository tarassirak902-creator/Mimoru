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
from app.games.spy.actions import record_spy_vote, spy_vote_map_lines
from app.games.spy.game import SpyGame, SpyPhase
from app.games.spy.keyboards import spy_finished_keyboard
from app.games.spy.presentation import (
    spy_public_text,
    spy_results_text,
    sync_spy_ui,
)
from app.services.access import can_manage_group


router = Router(name=__name__)
manager = GameManager()
engine = SpyGame()


async def _game_group(
    callback: CallbackQuery,
    session: AsyncSession,
    game_id: int,
):
    if callback.message is None:
        await callback.answer("Игровое сообщение недоступно.", show_alert=True)
        return None
    game = await manager.get_game(session, game_id=game_id)
    if game is None or game.game_type != "spy":
        await callback.answer("❌ Эта кнопка больше не активна.", show_alert=True)
        return None
    group = await session.get(Group, game.group_id)
    if (
        group is None
        or not group.is_active
        or callback.message.chat.id != group.telegram_chat_id
    ):
        await callback.answer(
            "❌ Эта кнопка относится к другой игровой сессии.",
            show_alert=True,
        )
        return None
    return game, group


async def _running_spy(
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
        await callback.answer(
            "⏳ Эта кнопка относится к прошлой фазе.",
            show_alert=True,
        )
        return None
    return game


async def _player(
    session: AsyncSession,
    game_id: int,
    user_id: int,
) -> GamePlayer | None:
    return await session.scalar(
        select(GamePlayer).where(
            GamePlayer.game_id == game_id,
            GamePlayer.user_telegram_id == user_id,
        )
    )


async def _can_start(
    bot: Bot,
    session: AsyncSession,
    group: Group,
    game,
    user_id: int,
) -> bool:
    if user_id == game.creator_telegram_id:
        return True
    if await can_manage_group(bot, group, user_id, session):
        return True
    settings = await session.get(GameGroupSettings, group.id)
    if settings is not None and settings.creator_policy == "any_at_min":
        player = await _player(session, game.id, user_id)
        return player is not None and player.status == "joined"
    return False


async def _can_control(
    bot: Bot,
    session: AsyncSession,
    group: Group,
    game,
    user_id: int,
) -> bool:
    return user_id == game.creator_telegram_id or await can_manage_group(
        bot,
        group,
        user_id,
        session,
    )


@router.callback_query(F.data == "gm:rules:spy")
async def spy_rules(callback: CallbackQuery) -> None:
    await callback.answer(
        "🕵️ Шпион: все, кроме одного игрока, знают общую локацию. "
        "Обсудите её, не называя напрямую, затем найдите Шпиона голосованием. "
        "Если его нашли, он может угадать локацию.",
        show_alert=True,
    )


@router.callback_query(F.data.regexp(r"^gm:ss:\d+$"))
async def spy_start(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    game_id = int((callback.data or "").rsplit(":", 1)[-1])
    resolved = await _game_group(callback, session, game_id)
    if resolved is None:
        return
    game, group = resolved
    if game.status != GameSessionStatus.LOBBY.value:
        await callback.answer("❌ Это лобби уже закрыто.", show_alert=True)
        return
    if not await _can_start(bot, session, group, game, callback.from_user.id):
        await callback.answer(
            "❌ У вас нет права запускать это лобби.",
            show_alert=True,
        )
        return
    try:
        game = await manager.start_lobby(session, game_id=game.id)
        await engine.start(session, game)
    except GamePlayerError:
        await callback.answer(
            "Для старта Шпиона нужно минимум 4 игрока.",
            show_alert=True,
        )
        return
    except Exception:
        locked = await manager.get_game(session, game_id=game.id, for_update=True)
        if locked is not None and locked.status == GameSessionStatus.RUNNING.value:
            locked.status = GameSessionStatus.RECOVERING.value
            locked.phase = "recovering"
            await session.commit()
        await callback.answer(
            "Игра сохранена для восстановления после ошибки запуска.",
            show_alert=True,
        )
        return
    await close_lobby_message(
        bot,
        session,
        group=group,
        game=game,
        text="▶️ 🕵️ Шпион начался.",
    )
    latest = await manager.get_game(session, game_id=game.id)
    if latest is not None:
        await sync_spy_ui(bot, session, latest)
    await callback.answer("▶️ Шпион начался")


@router.callback_query(F.data.regexp(r"^gm:sr:\d+:\d+$"))
async def spy_private_role(callback: CallbackQuery, session: AsyncSession) -> None:
    _, _, game_raw, phase_raw = (callback.data or "").split(":")
    game = await _running_spy(callback, session, int(game_raw), int(phase_raw))
    if game is None:
        return
    player = await _player(session, game.id, callback.from_user.id)
    if player is None or player.status != "alive":
        await callback.answer("❌ Вы не участвуете в этой игре.", show_alert=True)
        return
    state = dict(game.state_json or {})
    if player.role == "spy":
        text = (
            "🕵️ Вы — Шпион. Вы не знаете локацию. "
            "Слушайте остальных и постарайтесь не выдать себя."
        )
    else:
        text = (
            f"👥 Вы — местный. 📍 Локация: {state.get('location', 'неизвестно')}. "
            "Найдите Шпиона, не называя место напрямую."
        )
    await callback.answer(text[:200], show_alert=True)


@router.callback_query(F.data.regexp(r"^gm:svm:\d+:\d+$"))
async def spy_private_vote_map(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    _, _, game_raw, phase_raw = (callback.data or "").split(":")
    game = await _running_spy(callback, session, int(game_raw), int(phase_raw))
    if game is None:
        return
    if game.phase != SpyPhase.VOTING.value:
        await callback.answer("❌ Сейчас голосование не идёт.", show_alert=True)
        return
    try:
        lines = await spy_vote_map_lines(
            session,
            game=game,
            actor_user_id=callback.from_user.id,
        )
    except GameActionError:
        await callback.answer(
            "❌ Вы не участвуете в этом голосовании.",
            show_alert=True,
        )
        return
    await callback.answer(
        "Ваши номера:\n" + "\n".join(lines),
        show_alert=True,
    )


@router.callback_query(F.data.regexp(r"^gm:sv:\d+:\d+:\d+$"))
async def spy_vote(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    _, _, game_raw, phase_raw, number_raw = (callback.data or "").split(":")
    game = await _running_spy(callback, session, int(game_raw), int(phase_raw))
    if game is None:
        return
    if game.phase != SpyPhase.VOTING.value:
        await callback.answer("❌ Сейчас голосование не идёт.", show_alert=True)
        return
    try:
        _, created = await record_spy_vote(
            session,
            game=game,
            actor_user_id=callback.from_user.id,
            number=int(number_raw),
        )
    except GameActionError as error:
        text = str(error)
        if "actor" in text:
            text = "❌ Вы не участвуете в этой игре."
        elif "phase" in text:
            text = "❌ Этот ход уже завершён."
        else:
            text = "❌ Этот выбор больше недоступен."
        await callback.answer(text, show_alert=True)
        return
    if not created:
        await callback.answer("✅ Ваш голос уже принят.", show_alert=True)
        return
    latest = await manager.get_game(session, game_id=game.id)
    if latest is not None:
        await engine.maybe_advance_if_ready(session, latest)
        latest = await manager.get_game(session, game_id=game.id)
        if latest is not None:
            await sync_spy_ui(bot, session, latest)
    await callback.answer(f"✅ Голос принят: №{number_raw}", show_alert=True)


@router.callback_query(F.data.regexp(r"^gm:slm:\d+:\d+$"))
async def spy_location_map(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    _, _, game_raw, phase_raw = (callback.data or "").split(":")
    game = await _running_spy(callback, session, int(game_raw), int(phase_raw))
    if game is None:
        return
    state = dict(game.state_json or {})
    if (
        game.phase != SpyPhase.SPY_GUESS.value
        or callback.from_user.id != state.get("spy_user_id")
    ):
        await callback.answer("❌ Сейчас не ваш ход.", show_alert=True)
        return
    options = list(state.get("location_options") or [])
    lines = [f"{index} — {name}" for index, name in enumerate(options, start=1)]
    await callback.answer(
        "🗺 Варианты мест:\n" + "\n".join(lines),
        show_alert=True,
    )


@router.callback_query(F.data.regexp(r"^gm:sl:\d+:\d+:\d+$"))
async def spy_location_guess(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
) -> None:
    _, _, game_raw, phase_raw, number_raw = (callback.data or "").split(":")
    game = await _running_spy(callback, session, int(game_raw), int(phase_raw))
    if game is None:
        return
    try:
        _, created = await engine.guess_location(
            session,
            game,
            actor_telegram_id=callback.from_user.id,
            number=int(number_raw),
        )
    except PermissionError:
        await callback.answer("❌ Сейчас не ваш ход.", show_alert=True)
        return
    except ValueError:
        await callback.answer(
            "❌ Этот выбор больше недоступен.",
            show_alert=True,
        )
        return
    latest = await manager.get_game(session, game_id=game.id)
    if latest is not None:
        await sync_spy_ui(bot, session, latest)
    await callback.answer(
        "✅ Ответ принят." if created else "✅ Ваш ответ уже принят.",
        show_alert=True,
    )


@router.callback_query(F.data.regexp(r"^gm:sc:\d+:\d+$"))
async def spy_cancel_running(
    callback: CallbackQuery,
    bot: Bot,
    session: AsyncSession,
) -> None:
    _, _, game_raw, phase_raw = (callback.data or "").split(":")
    game = await _running_spy(callback, session, int(game_raw), int(phase_raw))
    if game is None:
        return
    group = await session.get(Group, game.group_id)
    if group is None or not await _can_control(
        bot,
        session,
        group,
        game,
        callback.from_user.id,
    ):
        await callback.answer(
            "❌ Отменить игру может создатель или администратор.",
            show_alert=True,
        )
        return
    game = await manager.cancel_game(
        session,
        game_id=game.id,
        reason="cancelled_by_user",
    )
    await sync_spy_ui(bot, session, game)
    await callback.answer("Игра отменена")


@router.callback_query(F.data.regexp(r"^gm:sres:\d+$"))
async def spy_results(callback: CallbackQuery, session: AsyncSession) -> None:
    game_id = int((callback.data or "").rsplit(":", 1)[-1])
    resolved = await _game_group(callback, session, game_id)
    if resolved is None or callback.message is None:
        return
    game, _ = resolved
    if game.status != GameSessionStatus.FINISHED.value:
        await callback.answer(
            "Результаты будут доступны после завершения игры.",
            show_alert=True,
        )
        return
    text = await spy_results_text(session, game)
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="◀️ К итогу",
                    callback_data=f"gm:sfinal:{game.id}",
                )
            ]
        ]
    )
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^gm:sfinal:\d+$"))
async def spy_final(callback: CallbackQuery, session: AsyncSession) -> None:
    game_id = int((callback.data or "").rsplit(":", 1)[-1])
    resolved = await _game_group(callback, session, game_id)
    if resolved is None or callback.message is None:
        return
    game, _ = resolved
    text = await spy_public_text(session, game)
    await callback.message.edit_text(
        text,
        reply_markup=spy_finished_keyboard(game.id),
    )
    await callback.answer()
