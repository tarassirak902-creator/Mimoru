from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.games.actions import GameActionError
from app.games.manager import GameManager
from app.games.mafia.actions import ensure_actor_targets, record_mafia_number_action, target_map_lines


router = Router(name=__name__)
manager = GameManager()


async def _running_mafia(callback: CallbackQuery, session: AsyncSession, game_id: int, phase_seq: int):
    if callback.message is None:
        await callback.answer("Игровое сообщение недоступно.", show_alert=True)
        return None
    game = await manager.get_game(session, game_id=game_id)
    if game is None or game.game_type != "mafia" or game.status != "running":
        await callback.answer("❌ Эта кнопка больше не активна.", show_alert=True)
        return None
    if game.phase_seq != phase_seq:
        await callback.answer("⏳ Эта кнопка относится к прошлой фазе.", show_alert=True)
        return None
    return game


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
    # Telegram limits answerCallbackQuery text to 200 characters.
    await callback.answer(text[:200], show_alert=True)


@router.callback_query(F.data.regexp(r"^gm:ma:\d+:\d+:\d+$"))
async def mafia_number_action(callback: CallbackQuery, session: AsyncSession) -> None:
    _, _, game_raw, phase_raw, number_raw = (callback.data or "").split(":")
    game = await _running_mafia(callback, session, int(game_raw), int(phase_raw))
    if game is None:
        return
    try:
        _, created = await record_mafia_number_action(
            session,
            game=game,
            actor_user_id=callback.from_user.id,
            number=int(number_raw),
        )
    except GameActionError as error:
        text = str(error)
        if "role has no" in text:
            text = "У вашей роли сейчас нет тайного действия."
        elif "target" in text:
            text = "Эта цель больше недоступна."
        else:
            text = "Сейчас этот выбор недоступен."
        await callback.answer(text, show_alert=True)
        return
    if created:
        await callback.answer("✅ Выбор принят и зафиксирован")
    else:
        await callback.answer("✅ Ваш выбор уже был принят")
