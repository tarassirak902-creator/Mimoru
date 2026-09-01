from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GameGroupSettings
from app.db.models import Group
from app.games.arena.game import ArenaGame, ArenaPhase
from app.games.arena.presentation import sync_arena_ui
from app.games.enums import GameSessionStatus
from app.games.lobby import close_lobby_message
from app.games.manager import GameManager, GamePlayerError
from app.services.access import can_manage_group

router = Router(name=__name__)
manager = GameManager()
engine = ArenaGame()


async def _resolve(callback: CallbackQuery, session: AsyncSession, game_id: int):
    if callback.message is None:
        return None
    game = await manager.get_game(session, game_id=game_id)
    if game is None or game.game_type != "arena":
        await callback.answer("❌ Кнопка больше не активна.", show_alert=True); return None
    group = await session.get(Group, game.group_id)
    if group is None or callback.message.chat.id != group.telegram_chat_id:
        await callback.answer("❌ Другая игровая сессия.", show_alert=True); return None
    return game, group


async def _turn(callback: CallbackQuery, session: AsyncSession, game_id: int, seq: int):
    resolved = await _resolve(callback, session, game_id)
    if resolved is None: return None
    game, _ = resolved
    if game.status != GameSessionStatus.RUNNING.value or game.phase != ArenaPhase.TURN.value:
        await callback.answer("❌ Бой уже завершён.", show_alert=True); return None
    if game.phase_seq != seq:
        await callback.answer("⏳ Это кнопка прошлого хода.", show_alert=True); return None
    return game


@router.callback_query(F.data == "gm:rules:arena")
async def rules(callback: CallbackQuery) -> None:
    await callback.answer("⚔️ Арена: у каждого 5 HP. В свой ход атакуйте соперника, защищайтесь или восстановите 1 HP. Защита полностью блокирует следующую атаку. Последний выживший побеждает.", show_alert=True)


@router.callback_query(F.data.regexp(r"^gm:as:\d+$"))
async def start(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    game_id = int((callback.data or "").rsplit(":", 1)[-1]); resolved = await _resolve(callback, session, game_id)
    if resolved is None: return
    game, group = resolved
    settings = await session.get(GameGroupSettings, group.id)
    allowed = callback.from_user.id == game.creator_telegram_id or await can_manage_group(bot, group, callback.from_user.id, session)
    if not allowed and settings is not None and settings.creator_policy == "any_at_min":
        allowed = any(p.user_telegram_id == callback.from_user.id and p.status == "joined" for p in await manager.list_players(session, game_id=game.id))
    if not allowed:
        await callback.answer("❌ Нет права запускать лобби.", show_alert=True); return
    try:
        game = await manager.start_lobby(session, game_id=game.id); await engine.start(session, game)
    except GamePlayerError:
        await callback.answer("Нужно минимум 2 игрока.", show_alert=True); return
    await close_lobby_message(bot, session, group=group, game=game, text="▶️ ⚔️ Бой на арене начался.")
    latest = await manager.get_game(session, game_id=game.id)
    if latest: await sync_arena_ui(bot, session, latest)
    await callback.answer("⚔️ Бой начался!")


async def _act(callback: CallbackQuery, bot: Bot, session: AsyncSession, game_id: int, seq: int, action: str, target: int | None = None) -> None:
    game = await _turn(callback, session, game_id, seq)
    if game is None: return
    try:
        result, created = await engine.act(session, game, actor_telegram_id=callback.from_user.id, action=action, target_id=target)
    except PermissionError:
        await callback.answer("❌ Сейчас не ваш ход.", show_alert=True); return
    except ValueError as exc:
        await callback.answer("❤️ HP уже полные." if "full" in str(exc) else "❌ Действие недоступно.", show_alert=True); return
    latest = await manager.get_game(session, game_id=game.id)
    if latest: await sync_arena_ui(bot, session, latest)
    labels = {"hit":"⚔️ Попадание!", "blocked":"🛡 Удар заблокирован.", "knockout":"💥 Соперник выбит!", "guard":"🛡 Защита активна.", "heal":"❤️ +1 HP", "winner":"🏆 Победа!"}
    await callback.answer(labels.get(result, "✅ Ход принят.") if created else "✅ Этот ход уже принят.", show_alert=True)


@router.callback_query(F.data.regexp(r"^gm:aa:\d+:\d+:\d+$"))
async def attack(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    _, _, gid, seq, target = (callback.data or "").split(":"); await _act(callback, bot, session, int(gid), int(seq), "attack", int(target))

@router.callback_query(F.data.regexp(r"^gm:ag:\d+:\d+$"))
async def guard(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    _, _, gid, seq = (callback.data or "").split(":"); await _act(callback, bot, session, int(gid), int(seq), "guard")

@router.callback_query(F.data.regexp(r"^gm:ah:\d+:\d+$"))
async def heal(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    _, _, gid, seq = (callback.data or "").split(":"); await _act(callback, bot, session, int(gid), int(seq), "heal")
