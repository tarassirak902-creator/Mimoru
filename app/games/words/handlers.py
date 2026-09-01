from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GameGroupSettings
from app.db.models import Group
from app.games.enums import GameSessionStatus
from app.games.lobby import close_lobby_message
from app.games.manager import GameManager, GamePlayerError
from app.games.words.game import WordsGame, WordsPhase
from app.games.words.presentation import sync_words_ui
from app.services.access import can_manage_group


router = Router(name=__name__)
manager = GameManager()
engine = WordsGame()


async def _resolve(callback: CallbackQuery, session: AsyncSession, game_id: int):
    if callback.message is None:
        await callback.answer("Игровое сообщение недоступно.", show_alert=True)
        return None
    game = await manager.get_game(session, game_id=game_id)
    if game is None or game.game_type != "words":
        await callback.answer("❌ Эта кнопка больше не активна.", show_alert=True)
        return None
    group = await session.get(Group, game.group_id)
    if group is None or not group.is_active or callback.message.chat.id != group.telegram_chat_id:
        await callback.answer("❌ Эта кнопка относится к другой игровой сессии.", show_alert=True)
        return None
    return game, group


async def _turn(callback: CallbackQuery, session: AsyncSession, game_id: int, phase_seq: int):
    resolved = await _resolve(callback, session, game_id)
    if resolved is None:
        return None
    game, _ = resolved
    if game.status != GameSessionStatus.RUNNING.value or game.phase != WordsPhase.TURN.value:
        await callback.answer("❌ Игра уже завершена.", show_alert=True)
        return None
    if game.phase_seq != phase_seq:
        await callback.answer("⏳ Эта кнопка относится к прошлому ходу.", show_alert=True)
        return None
    return game


async def _can_start(bot: Bot, session: AsyncSession, group: Group, game, user_id: int) -> bool:
    if user_id == game.creator_telegram_id:
        return True
    if await can_manage_group(bot, group, user_id, session):
        return True
    settings = await session.get(GameGroupSettings, group.id)
    if settings is None or settings.creator_policy != "any_at_min":
        return False
    return any(
        player.user_telegram_id == user_id and player.status == "joined"
        for player in await manager.list_players(session, game_id=game.id)
    )


@router.callback_query(F.data == "gm:rules:words")
async def words_rules(callback: CallbackQuery) -> None:
    await callback.answer(
        "🔤 Слова: продолжайте цепочку на последнюю значимую букву. В свой ход откройте персональные варианты и выберите номер. Повторы исключены. После 3 пропусков или таймаутов игрок выбывает.",
        show_alert=True,
    )


@router.callback_query(F.data.regexp(r"^gm:ws:\d+$"))
async def words_start(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    game_id = int((callback.data or "").rsplit(":", 1)[-1])
    resolved = await _resolve(callback, session, game_id)
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
        await callback.answer("Для игры нужно минимум 2 игрока.", show_alert=True)
        return
    except Exception:
        locked = await manager.get_game(session, game_id=game.id, for_update=True)
        if locked is not None and locked.status == GameSessionStatus.RUNNING.value:
            locked.status = GameSessionStatus.RECOVERING.value
            locked.phase = "recovering"
            await session.commit()
        await callback.answer("Игра сохранена для восстановления после ошибки запуска.", show_alert=True)
        return
    await close_lobby_message(bot, session, group=group, game=game, text="▶️ 🔤 Игра «Слова» началась.")
    latest = await manager.get_game(session, game_id=game.id)
    if latest is not None:
        await sync_words_ui(bot, session, latest)
    await callback.answer("🔤 Игра началась")


@router.callback_query(F.data.regexp(r"^gm:wo:\d+:\d+$"))
async def words_options(callback: CallbackQuery, session: AsyncSession) -> None:
    _, _, game_raw, phase_raw = (callback.data or "").split(":")
    game = await _turn(callback, session, int(game_raw), int(phase_raw))
    if game is None:
        return
    state = dict(game.state_json or {})
    if callback.from_user.id != int(state.get("turn_user_id") or 0):
        await callback.answer("❌ Сейчас не ваш ход.", show_alert=True)
        return
    options = list(state.get("options") or [])
    if not options:
        await callback.answer("Вариантов нет — пропустите ход.", show_alert=True)
        return
    lines = [f"🔤 Буква: {str(state.get('required_letter') or '?').upper()}", ""]
    lines.extend(f"{index}. {word}" for index, word in enumerate(options, start=1))
    lines.extend(["", "Выберите этот номер в игровом сообщении."])
    await callback.answer("\n".join(lines), show_alert=True)


@router.callback_query(F.data.regexp(r"^gm:wp:\d+:\d+:\d+$"))
async def words_pick(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    _, _, game_raw, phase_raw, number_raw = (callback.data or "").split(":")
    game = await _turn(callback, session, int(game_raw), int(phase_raw))
    if game is None:
        return
    try:
        word, created = await engine.pick_word(
            session,
            game,
            actor_telegram_id=callback.from_user.id,
            number=int(number_raw),
        )
    except PermissionError:
        await callback.answer("❌ Сейчас не ваш ход.", show_alert=True)
        return
    except ValueError:
        await callback.answer("❌ Этот вариант сейчас недоступен.", show_alert=True)
        return
    latest = await manager.get_game(session, game_id=game.id)
    if latest is not None:
        await sync_words_ui(bot, session, latest)
    await callback.answer(f"✅ Принято: {word}" if created else "✅ Этот ход уже принят.", show_alert=True)


@router.callback_query(F.data.regexp(r"^gm:wskip:\d+:\d+$"))
async def words_skip(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    _, _, game_raw, phase_raw = (callback.data or "").split(":")
    game = await _turn(callback, session, int(game_raw), int(phase_raw))
    if game is None:
        return
    try:
        _, created = await engine.skip_turn(session, game, actor_telegram_id=callback.from_user.id)
    except PermissionError:
        await callback.answer("❌ Сейчас не ваш ход.", show_alert=True)
        return
    except ValueError:
        await callback.answer("❌ Этот ход больше недоступен.", show_alert=True)
        return
    latest = await manager.get_game(session, game_id=game.id)
    if latest is not None:
        await sync_words_ui(bot, session, latest)
    await callback.answer("⏭ Пропуск записан." if created else "✅ Этот ход уже принят.", show_alert=True)
