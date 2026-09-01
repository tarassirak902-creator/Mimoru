from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GameGroupSettings
from app.db.models import Group
from app.games.detective.game import DetectiveGame, DetectivePhase
from app.games.detective.presentation import sync_detective_ui
from app.games.enums import GameSessionStatus
from app.games.lobby import close_lobby_message
from app.games.manager import GameManager, GamePlayerError
from app.services.access import can_manage_group


router = Router(name=__name__)
manager = GameManager()
engine = DetectiveGame()


async def _resolve(callback: CallbackQuery, session: AsyncSession, game_id: int):
    if callback.message is None:
        await callback.answer("Игровое сообщение недоступно.", show_alert=True)
        return None
    game = await manager.get_game(session, game_id=game_id)
    if game is None or game.game_type != "detective":
        await callback.answer("❌ Эта кнопка больше не активна.", show_alert=True)
        return None
    group = await session.get(Group, game.group_id)
    if group is None or not group.is_active or callback.message.chat.id != group.telegram_chat_id:
        await callback.answer("❌ Эта кнопка относится к другой игровой сессии.", show_alert=True)
        return None
    return game, group


async def _round(callback: CallbackQuery, session: AsyncSession, game_id: int, phase_seq: int):
    resolved = await _resolve(callback, session, game_id)
    if resolved is None:
        return None
    game, _ = resolved
    if game.status != GameSessionStatus.RUNNING.value or game.phase != DetectivePhase.INVESTIGATION.value:
        await callback.answer("❌ Это дело уже закрыто.", show_alert=True)
        return None
    if game.phase_seq != phase_seq:
        await callback.answer("⏳ Эта кнопка относится к прошлому делу.", show_alert=True)
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


@router.callback_query(F.data == "gm:rules:detective")
async def detective_rules(callback: CallbackQuery) -> None:
    await callback.answer(
        "🕵️ Детектив: изучайте три улики через персональные popup, затем откройте список подозреваемых и выберите номер. За верное обвинение — 1 очко. После нескольких дел побеждает лучший сыщик.",
        show_alert=True,
    )


@router.callback_query(F.data.regexp(r"^gm:ds:\d+$"))
async def detective_start(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
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
        await callback.answer("Для Детектива нужно минимум 2 игрока.", show_alert=True)
        return
    except Exception:
        locked = await manager.get_game(session, game_id=game.id, for_update=True)
        if locked is not None and locked.status == GameSessionStatus.RUNNING.value:
            locked.status = GameSessionStatus.RECOVERING.value
            locked.phase = "recovering"
            await session.commit()
        await callback.answer("Игра сохранена для восстановления после ошибки запуска.", show_alert=True)
        return
    await close_lobby_message(bot, session, group=group, game=game, text="▶️ 🕵️ Расследование началось.")
    latest = await manager.get_game(session, game_id=game.id)
    if latest is not None:
        await sync_detective_ui(bot, session, latest)
    await callback.answer("🕵️ Расследование началось")


def _current_case(game) -> dict:
    state = dict(game.state_json or {})
    cases = list(state.get("cases") or [])
    index = int(state.get("case_index") or 0)
    return dict(cases[index]) if 0 <= index < len(cases) else {}


@router.callback_query(F.data.regexp(r"^gm:dc:\d+:\d+:\d+$"))
async def detective_clue(callback: CallbackQuery, session: AsyncSession) -> None:
    _, _, game_raw, phase_raw, clue_raw = (callback.data or "").split(":")
    game = await _round(callback, session, int(game_raw), int(phase_raw))
    if game is None:
        return
    clues = list(_current_case(game).get("clues") or [])
    clue_number = int(clue_raw)
    if clue_number < 1 or clue_number > len(clues):
        await callback.answer("Улика недоступна.", show_alert=True)
        return
    await callback.answer(f"🔎 Улика {clue_number}\n\n{clues[clue_number - 1]}", show_alert=True)


@router.callback_query(F.data.regexp(r"^gm:dsus:\d+:\d+$"))
async def detective_suspects(callback: CallbackQuery, session: AsyncSession) -> None:
    _, _, game_raw, phase_raw = (callback.data or "").split(":")
    game = await _round(callback, session, int(game_raw), int(phase_raw))
    if game is None:
        return
    suspects = list(_current_case(game).get("suspects") or [])
    lines = ["👥 Подозреваемые", ""]
    lines.extend(f"{index}. {name}" for index, name in enumerate(suspects, start=1))
    lines.extend(["", "Выберите номер в игровом сообщении."])
    await callback.answer("\n".join(lines), show_alert=True)


@router.callback_query(F.data.regexp(r"^gm:da:\d+:\d+:\d+$"))
async def detective_accuse(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    _, _, game_raw, phase_raw, number_raw = (callback.data or "").split(":")
    game = await _round(callback, session, int(game_raw), int(phase_raw))
    if game is None:
        return
    try:
        _, created = await engine.accuse(
            session,
            game,
            actor_telegram_id=callback.from_user.id,
            number=int(number_raw),
        )
    except PermissionError:
        await callback.answer("❌ Вы не участвуете в этой игре.", show_alert=True)
        return
    except ValueError:
        await callback.answer("❌ Этот вариант больше недоступен.", show_alert=True)
        return
    if created:
        await engine.maybe_advance_if_ready(session, game)
    latest = await manager.get_game(session, game_id=game.id)
    if latest is not None:
        await sync_detective_ui(bot, session, latest)
    await callback.answer("✅ Обвинение принято." if created else "✅ Ваше обвинение уже принято.", show_alert=True)
