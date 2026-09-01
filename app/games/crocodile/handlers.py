from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GameGroupSettings, GamePlayer
from app.db.models import Group
from app.games.crocodile.game import CrocodileGame, CrocodilePhase
from app.games.crocodile.keyboards import crocodile_finished_keyboard
from app.games.crocodile.presentation import (
    crocodile_public_text,
    crocodile_results_text,
    sync_crocodile_ui,
)
from app.games.enums import GameSessionStatus
from app.games.lobby import close_lobby_message
from app.games.manager import GameManager, GamePlayerError
from app.games.targets import ensure_target_map, resolve_target_number
from app.services.access import can_manage_group


router = Router(name=__name__)
manager = GameManager()
engine = CrocodileGame()
_TARGET_PAGE_SIZE = 5


async def _game_group(callback: CallbackQuery, session: AsyncSession, game_id: int):
    if callback.message is None:
        await callback.answer("Игровое сообщение недоступно.", show_alert=True)
        return None
    game = await manager.get_game(session, game_id=game_id)
    if game is None or game.game_type != "crocodile":
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
    if game.status != GameSessionStatus.RUNNING.value or game.phase != CrocodilePhase.ROUND.value:
        await callback.answer("❌ Эта кнопка больше не активна.", show_alert=True)
        return None
    if game.phase_seq != phase_seq:
        await callback.answer("⏳ Эта кнопка относится к прошлому раунду.", show_alert=True)
        return None
    return game


async def _player(session: AsyncSession, game_id: int, user_id: int) -> GamePlayer | None:
    return await session.scalar(
        select(GamePlayer).where(
            GamePlayer.game_id == game_id,
            GamePlayer.user_telegram_id == user_id,
        )
    )


async def _alive_players(session: AsyncSession, game_id: int) -> list[GamePlayer]:
    return list(
        (
            await session.scalars(
                select(GamePlayer)
                .where(GamePlayer.game_id == game_id, GamePlayer.status == "alive")
                .order_by(GamePlayer.id)
            )
        ).all()
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


async def _require_host(callback: CallbackQuery, game) -> bool:
    state = dict(game.state_json or {})
    if callback.from_user.id != int(state.get("host_user_id") or 0):
        await callback.answer("❌ Сейчас вы не ведущий.", show_alert=True)
        return False
    return True


async def _target_map(session: AsyncSession, game, host_id: int):
    players = await _alive_players(session, game.id)
    targets = [player.user_telegram_id for player in players if player.user_telegram_id != host_id]
    rows = await ensure_target_map(
        session,
        game_id=game.id,
        phase_seq=game.phase_seq,
        actor_telegram_id=host_id,
        target_telegram_ids=targets,
    )
    names = {player.user_telegram_id: player.display_name for player in players}
    return rows, names


@router.callback_query(F.data == "gm:rules:crocodile")
async def crocodile_rules(callback: CallbackQuery) -> None:
    await callback.answer(
        "🐊 Крокодил: каждый игрок по очереди становится ведущим и получает секретное слово. "
        "Он объясняет/показывает его в обычном чате. Бот не читает догадки как команды. "
        "Когда слово угадано, ведущий отмечает угадавшего кнопкой. За успешный раунд оба получают по 1 очку.",
        show_alert=True,
    )


@router.callback_query(F.data.regexp(r"^gm:ccs:\d+$"))
async def crocodile_start(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
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
        await callback.answer("Для Крокодила нужно минимум 3 игрока.", show_alert=True)
        return
    except Exception:
        locked = await manager.get_game(session, game_id=game.id, for_update=True)
        if locked is not None and locked.status == GameSessionStatus.RUNNING.value:
            locked.status = GameSessionStatus.RECOVERING.value
            locked.phase = "recovering"
            await session.commit()
        await callback.answer("Игра сохранена для восстановления после ошибки запуска.", show_alert=True)
        return
    await close_lobby_message(bot, session, group=group, game=game, text="▶️ 🐊 Крокодил начался.")
    latest = await manager.get_game(session, game_id=game.id)
    if latest is not None:
        await sync_crocodile_ui(bot, session, latest)
    await callback.answer("▶️ Крокодил начался")


@router.callback_query(F.data.regexp(r"^gm:cw:\d+:\d+$"))
async def crocodile_word(callback: CallbackQuery, session: AsyncSession) -> None:
    _, _, game_raw, phase_raw = (callback.data or "").split(":")
    game = await _running(callback, session, int(game_raw), int(phase_raw))
    if game is None or not await _require_host(callback, game):
        return
    state = dict(game.state_json or {})
    word = str(state.get("current_word") or "")
    await callback.answer(f"🎭 Ваше слово:\n{word}", show_alert=True)


@router.callback_query(F.data.regexp(r"^gm:cl:\d+:\d+:\d+$"))
async def crocodile_target_list(callback: CallbackQuery, session: AsyncSession) -> None:
    _, _, game_raw, phase_raw, page_raw = (callback.data or "").split(":")
    game = await _running(callback, session, int(game_raw), int(phase_raw))
    if game is None or not await _require_host(callback, game):
        return
    rows, names = await _target_map(session, game, callback.from_user.id)
    page = max(0, int(page_raw))
    start = page * _TARGET_PAGE_SIZE
    chunk = rows[start:start + _TARGET_PAGE_SIZE]
    if not chunk:
        await callback.answer("На этой странице нет игроков.", show_alert=True)
        return
    total_pages = (len(rows) + _TARGET_PAGE_SIZE - 1) // _TARGET_PAGE_SIZE
    lines = [f"👥 Кто угадал? · {page + 1}/{total_pages}"]
    for row in chunk:
        name = str(names.get(row.target_telegram_id) or f"Игрок {row.target_telegram_id}")
        if len(name) > 22:
            name = name[:19] + "…"
        lines.append(f"{row.number} — {name}")
    await callback.answer("\n".join(lines), show_alert=True)


@router.callback_query(F.data.regexp(r"^gm:ct:\d+:\d+:\d+$"))
async def crocodile_target(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    _, _, game_raw, phase_raw, number_raw = (callback.data or "").split(":")
    game = await _running(callback, session, int(game_raw), int(phase_raw))
    if game is None or not await _require_host(callback, game):
        return
    await _target_map(session, game, callback.from_user.id)
    target_id = await resolve_target_number(
        session,
        game_id=game.id,
        phase_seq=game.phase_seq,
        actor_telegram_id=callback.from_user.id,
        number=int(number_raw),
    )
    if target_id is None:
        await callback.answer("❌ Такой номер сейчас недоступен.", show_alert=True)
        return
    try:
        created = await engine.mark_guessed(
            session,
            game,
            actor_telegram_id=callback.from_user.id,
            guesser_telegram_id=target_id,
        )
    except (PermissionError, ValueError):
        await callback.answer("❌ Этот выбор больше недоступен.", show_alert=True)
        return
    latest = await manager.get_game(session, game_id=game.id)
    if latest is not None:
        await sync_crocodile_ui(bot, session, latest)
    await callback.answer("✅ Угаданный игрок отмечен." if created else "✅ Результат уже принят.", show_alert=True)


@router.callback_query(F.data.regexp(r"^gm:ck:\d+:\d+$"))
async def crocodile_skip(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    _, _, game_raw, phase_raw = (callback.data or "").split(":")
    game = await _running(callback, session, int(game_raw), int(phase_raw))
    if game is None or not await _require_host(callback, game):
        return
    try:
        changed = await engine.skip_round(session, game, actor_telegram_id=callback.from_user.id)
    except (PermissionError, ValueError):
        await callback.answer("❌ Этот раунд уже завершён.", show_alert=True)
        return
    latest = await manager.get_game(session, game_id=game.id)
    if latest is not None:
        await sync_crocodile_ui(bot, session, latest)
    await callback.answer("⏭ Слово пропущено." if changed else "Раунд уже завершён.")


@router.callback_query(F.data.regexp(r"^gm:ccancel:\d+:\d+$"))
async def crocodile_cancel(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
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
    await sync_crocodile_ui(bot, session, game)
    await callback.answer("Игра отменена")


@router.callback_query(F.data.regexp(r"^gm:cres:\d+$"))
async def crocodile_results(callback: CallbackQuery, session: AsyncSession) -> None:
    game_id = int((callback.data or "").rsplit(":", 1)[-1])
    resolved = await _game_group(callback, session, game_id)
    if resolved is None or callback.message is None:
        return
    game, _ = resolved
    if game.status != GameSessionStatus.FINISHED.value:
        await callback.answer("Результаты доступны после завершения игры.", show_alert=True)
        return
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="◀️ К итогу", callback_data=f"gm:cfinal:{game.id}")
        ]]
    )
    await callback.message.edit_text(await crocodile_results_text(session, game), reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^gm:cfinal:\d+$"))
async def crocodile_final(callback: CallbackQuery, session: AsyncSession) -> None:
    game_id = int((callback.data or "").rsplit(":", 1)[-1])
    resolved = await _game_group(callback, session, game_id)
    if resolved is None or callback.message is None:
        return
    game, _ = resolved
    await callback.message.edit_text(
        await crocodile_public_text(session, game),
        reply_markup=crocodile_finished_keyboard(game.id),
    )
    await callback.answer()
