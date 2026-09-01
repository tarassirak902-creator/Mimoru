from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GameGroupSettings, GamePlayer
from app.db.models import Group
from app.games.cards.game import CardsGame, CardsPhase, card_label
from app.games.cards.keyboards import cards_finished_keyboard
from app.games.cards.presentation import cards_public_text, cards_results_text, sync_cards_ui
from app.games.enums import GameSessionStatus
from app.games.lobby import close_lobby_message
from app.games.manager import GameManager, GamePlayerError
from app.services.access import can_manage_group


router = Router(name=__name__)
manager = GameManager()
engine = CardsGame()
_PAGE_SIZE = 5


async def _game_group(callback: CallbackQuery, session: AsyncSession, game_id: int):
    if callback.message is None:
        await callback.answer("Игровое сообщение недоступно.", show_alert=True)
        return None
    game = await manager.get_game(session, game_id=game_id)
    if game is None or game.game_type != "cards":
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
    if game.status != GameSessionStatus.RUNNING.value or game.phase != CardsPhase.TURN.value:
        await callback.answer("❌ Эта кнопка больше не активна.", show_alert=True)
        return None
    if game.phase_seq != phase_seq:
        await callback.answer("⏳ Эта кнопка относится к прошлому ходу.", show_alert=True)
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


@router.callback_query(F.data == "gm:rules:cards")
async def cards_rules(callback: CallbackQuery) -> None:
    await callback.answer(
        "🃏 Карты: положите карту того же цвета или значения. ⛔ пропускает игрока, 🔄 меняет направление, +2 даёт следующему две карты. Побеждает тот, кто первым избавится от всех карт.",
        show_alert=True,
    )


@router.callback_query(F.data.regexp(r"^gm:cgs:\d+$"))
async def cards_start(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
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
        await callback.answer("Для карточной игры нужно минимум 2 игрока.", show_alert=True)
        return
    except Exception:
        locked = await manager.get_game(session, game_id=game.id, for_update=True)
        if locked is not None and locked.status == GameSessionStatus.RUNNING.value:
            locked.status = GameSessionStatus.RECOVERING.value
            locked.phase = "recovering"
            await session.commit()
        await callback.answer("Игра сохранена для восстановления после ошибки запуска.", show_alert=True)
        return
    await close_lobby_message(bot, session, group=group, game=game, text="▶️ 🃏 Карточная игра началась.")
    latest = await manager.get_game(session, game_id=game.id)
    if latest is not None:
        await sync_cards_ui(bot, session, latest)
    await callback.answer("▶️ Карточная игра началась")


@router.callback_query(F.data.regexp(r"^gm:ch:\d+:\d+:\d+$"))
async def cards_hand(callback: CallbackQuery, session: AsyncSession) -> None:
    _, _, game_raw, phase_raw, page_raw = (callback.data or "").split(":")
    game = await _running(callback, session, int(game_raw), int(phase_raw))
    if game is None:
        return
    player = await _player(session, game.id, callback.from_user.id)
    if player is None or player.status != "alive":
        await callback.answer("❌ Вы не участвуете в этой игре.", show_alert=True)
        return
    state = dict(game.state_json or {})
    hand = list(dict(state.get("hands") or {}).get(str(callback.from_user.id)) or [])
    page = max(0, int(page_raw))
    start = page * _PAGE_SIZE
    chunk = hand[start:start + _PAGE_SIZE]
    top = list(state.get("discard") or [])[-1]
    lines = [f"🃏 Ваша рука · {len(hand)} карт", f"Стол: {card_label(top)}", ""]
    for index, card in enumerate(chunk, start=start):
        marker = "✅" if card.split(":", 1)[0] == top.split(":", 1)[0] or card.split(":", 1)[1] == top.split(":", 1)[1] else "▫️"
        lines.append(f"{index + 1}. {marker} {card_label(card)}")
    if callback.from_user.id == int(state.get("turn_user_id") or 0):
        lines.append("\nНажмите номер карты в общем сообщении. ✅ = можно сыграть.")
    else:
        lines.append("\nСейчас ход другого игрока.")
    await callback.answer("\n".join(lines), show_alert=True)


@router.callback_query(F.data.regexp(r"^gm:cp:\d+:\d+:\d+$"))
async def cards_play(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    _, _, game_raw, phase_raw, number_raw = (callback.data or "").split(":")
    game = await _running(callback, session, int(game_raw), int(phase_raw))
    if game is None:
        return
    try:
        result, created = await engine.play_card(session, game, actor_telegram_id=callback.from_user.id, card_index=int(number_raw) - 1)
    except PermissionError:
        await callback.answer("❌ Сейчас не ваш ход.", show_alert=True)
        return
    except ValueError:
        await callback.answer("❌ Эту карту сейчас нельзя сыграть.", show_alert=True)
        return
    latest = await manager.get_game(session, game_id=game.id)
    if latest is not None:
        await sync_cards_ui(bot, session, latest)
    await callback.answer("🏆 Вы избавились от всех карт!" if result == "winner" else "✅ Карта сыграна." if created else "✅ Этот ход уже принят.", show_alert=True)


@router.callback_query(F.data.regexp(r"^gm:cd:\d+:\d+$"))
async def cards_draw(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    _, _, game_raw, phase_raw = (callback.data or "").split(":")
    game = await _running(callback, session, int(game_raw), int(phase_raw))
    if game is None:
        return
    try:
        result, created = await engine.draw_card(session, game, actor_telegram_id=callback.from_user.id)
    except PermissionError:
        await callback.answer("❌ Сейчас не ваш ход.", show_alert=True)
        return
    except ValueError:
        await callback.answer("❌ Этот ход больше недоступен.", show_alert=True)
        return
    latest = await manager.get_game(session, game_id=game.id)
    if latest is not None:
        await sync_cards_ui(bot, session, latest)
    text = "➕ Карта взята. Ход передан." if result == "drawn" else "Колода пуста. Ход передан."
    await callback.answer(text if created else "✅ Этот ход уже принят.", show_alert=True)


@router.callback_query(F.data.regexp(r"^gm:cgres:\d+$"))
async def cards_results(callback: CallbackQuery, session: AsyncSession) -> None:
    game_id = int((callback.data or "").rsplit(":", 1)[-1])
    resolved = await _game_group(callback, session, game_id)
    if resolved is None or callback.message is None:
        return
    game, _ = resolved
    if game.status != GameSessionStatus.FINISHED.value:
        await callback.answer("Результаты будут доступны после завершения игры.", show_alert=True)
        return
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ К итогу", callback_data=f"gm:cgfinal:{game.id}")]
    ])
    await callback.message.edit_text(await cards_results_text(session, game), reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^gm:cgfinal:\d+$"))
async def cards_final(callback: CallbackQuery, session: AsyncSession) -> None:
    game_id = int((callback.data or "").rsplit(":", 1)[-1])
    resolved = await _game_group(callback, session, game_id)
    if resolved is None or callback.message is None:
        return
    game, _ = resolved
    await callback.message.edit_text(await cards_public_text(session, game), reply_markup=cards_finished_keyboard(game.id))
    await callback.answer()
