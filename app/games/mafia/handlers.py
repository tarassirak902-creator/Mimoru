from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GamePlayer
from app.db.models import Group
from app.games.actions import GameActionError
from app.games.manager import GameManager
from app.games.mafia.actions import record_mafia_number_action, target_map_lines
from app.games.mafia.game import MafiaGame
from app.games.mafia.presentation import sync_mafia_ui


router = Router(name=__name__)
manager = GameManager()
engine = MafiaGame()

ROLE_LABELS = {
    "civilian": "👨 Мирный житель",
    "mafia": "🔪 Мафия",
    "doctor": "🩺 Доктор",
    "commissioner": "🕵️ Комиссар",
}


async def _running_mafia(
    callback: CallbackQuery,
    session: AsyncSession,
    game_id: int,
    phase_seq: int,
):
    if callback.message is None:
        await callback.answer("Игровое сообщение недоступно.", show_alert=True)
        return None
    game = await manager.get_game(session, game_id=game_id)
    if game is None or game.game_type != "mafia" or game.status != "running":
        await callback.answer("❌ Эта кнопка больше не активна.", show_alert=True)
        return None
    group = await session.get(Group, game.group_id)
    if group is None or not group.is_active or callback.message.chat.id != group.telegram_chat_id:
        await callback.answer("❌ Эта кнопка относится к другой игровой сессии.", show_alert=True)
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
            names = ", ".join(mate.display_name for mate in teammates)
            text += f"\nСоюзники: {names}."
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
    page = int(page_raw)
    start, end = (1, 7) if page == 1 else (8, 15)
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
    text = "Ваши номера:\n" + "\n".join(lines)
    await callback.answer(text[:200], show_alert=True)


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
    if created and player is not None and player.role == "commissioner" and action.target_telegram_id is not None:
        target = await _player(session, game.id, action.target_telegram_id)
        response = "🔎 Результат: игрок относится к Мафии." if target and target.team == "mafia" else "🔎 Результат: игрок не относится к Мафии."

    if created:
        await engine.maybe_advance_if_ready(session, game)
        latest = await manager.get_game(session, game_id=game.id)
        if latest is not None:
            await sync_mafia_ui(bot, session, latest)
    await callback.answer(response[:200], show_alert=player is not None and player.role == "commissioner")
