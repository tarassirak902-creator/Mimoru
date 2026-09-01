from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GamePlayer, GameSession
from app.db.models import Group
from app.games.arena.keyboards import arena_finished_keyboard, arena_keyboard
from app.games.enums import GameSessionStatus
from app.games.messages import upsert_phase_message
from app.games.panels import ensure_game_panel


async def arena_text(session: AsyncSession, game: GameSession) -> tuple[str, list[tuple[int, str]]]:
    players = list((await session.scalars(select(GamePlayer).where(GamePlayer.game_id == game.id).order_by(GamePlayer.id))).all())
    by_id = {p.user_telegram_id: p for p in players}
    state = dict(game.state_json or {})
    if game.status == GameSessionStatus.FINISHED.value:
        winner_id = int((game.finish_reason or "0").split(":")[-1])
        winner = by_id.get(winner_id)
        return f"🏆 АРЕНА ЗАВЕРШЕНА\n\nПобедитель: {winner.display_name if winner else 'игрок'}\nХодов: {game.round_no}\n\nРезультат сохранён в статистике и рейтинге.", []
    turn_id = int(state.get("turn_user_id") or 0)
    turn = by_id.get(turn_id)
    lines = ["⚔️ АРЕНА", "", f"👉 Ход: {turn.display_name if turn else 'игрок'}", f"🔄 Ход №{game.round_no}", "", "Бойцы:"]
    targets = []
    for p in players:
        ps = dict(p.state_json or {})
        hp = int(ps.get("hp") or 0)
        status = "💀" if p.status != "alive" else "🛡" if ps.get("guard") else "❤️"
        lines.append(f"• {p.display_name} — {status} {hp}/5 · урон {p.score}")
        if p.status == "alive" and p.user_telegram_id != turn_id:
            targets.append((p.user_telegram_id, p.display_name))
    last = dict(state.get("last_action") or {})
    if last:
        actor = by_id.get(int(last.get("user_id") or 0))
        result = last.get("result")
        if result in {"hit", "knockout", "blocked"}:
            target = by_id.get(int(last.get("target_id") or 0))
            verb = "пробил" if result == "hit" else "выбил" if result == "knockout" else "атаковал, но удар заблокирован у"
            lines.extend(["", f"⚔️ {actor.display_name if actor else 'Игрок'} {verb} {target.display_name if target else 'цель'}."])
        elif result == "guard":
            lines.extend(["", f"🛡 {actor.display_name if actor else 'Игрок'} занял защитную стойку."])
        elif result == "heal":
            lines.extend(["", f"❤️ {actor.display_name if actor else 'Игрок'} восстановил 1 HP."])
    return "\n".join(lines), targets


async def sync_arena_ui(bot: Bot, session: AsyncSession, game: GameSession) -> None:
    game = await session.get(GameSession, game.id)
    if game is None:
        return
    group = await session.get(Group, game.group_id)
    if group is None or not group.is_active:
        return
    text, targets = await arena_text(session, game)
    markup = arena_finished_keyboard() if game.status == GameSessionStatus.FINISHED.value else arena_keyboard(game.id, game.phase_seq, targets)
    await upsert_phase_message(bot, session, game_id=game.id, chat_id=group.telegram_chat_id, text=text, reply_markup=markup, kind="phase")
    await ensure_game_panel(bot, session, group=group, pin=False)
