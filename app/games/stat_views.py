from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.game_models import GamePlayerGameStats, GamePlayerStats, GameResult
from app.games.registry import game_registry
from app.services.public_identity import public_user_token


def _game_title(game_type: str) -> str:
    definition = game_registry.get(game_type)
    return definition.title if definition is not None else game_type


async def render_member_game_stats(
    session: AsyncSession,
    *,
    group_id: int,
    user_id: int,
    label: str | None = None,
) -> str:
    label = label or public_user_token(user_id)
    stats = await session.scalar(
        select(GamePlayerStats).where(
            GamePlayerStats.group_id == group_id,
            GamePlayerStats.user_telegram_id == user_id,
        )
    )
    if stats is None:
        return (
            f"🎮 ИГРОВАЯ СТАТИСТИКА — {label}\n\n"
            "🎲 Игр: 0\n"
            "🏆 Побед: 0\n"
            "💀 Поражений: 0\n"
            "⭐ Рейтинг: 1000\n"
            "🔥 Серия побед: 0\n"
            "🏅 Лучшая серия: 0\n\n"
            "Завершённых игровых партий в этой группе пока нет."
        )

    per_game = list((await session.scalars(
        select(GamePlayerGameStats)
        .where(
            GamePlayerGameStats.group_id == group_id,
            GamePlayerGameStats.user_telegram_id == user_id,
        )
        .order_by(
            GamePlayerGameStats.games_played.desc(),
            GamePlayerGameStats.game_type,
        )
        .limit(10)
    )).all())

    lines = [
        f"🎮 ИГРОВАЯ СТАТИСТИКА — {label}",
        "",
        f"🎲 Игр: {stats.games_played}",
        f"🏆 Побед: {stats.wins}",
        f"💀 Поражений: {stats.losses}",
        f"⭐ Рейтинг: {stats.rating}",
        f"🔥 Серия побед: {stats.win_streak}",
        f"🏅 Лучшая серия: {stats.best_win_streak}",
    ]
    if per_game:
        lines.extend(["", "По играм:"])
        for row in per_game:
            lines.append(
                f"• {_game_title(row.game_type)} — "
                f"{row.wins} побед / {row.games_played} игр · ⭐ {row.rating}"
            )
    lines.extend(["", "Здесь учитываются только полноценные игры Mimoru в этой группе."])
    return "\n".join(lines)


async def render_group_game_stats(session: AsyncSession, *, group_id: int) -> str:
    completed = int(
        await session.scalar(
            select(func.count(GameResult.id)).where(GameResult.group_id == group_id)
        )
        or 0
    )
    players = int(
        await session.scalar(
            select(func.count(GamePlayerStats.id)).where(GamePlayerStats.group_id == group_id)
        )
        or 0
    )
    game_rows = (
        await session.execute(
            select(GameResult.game_type, func.count(GameResult.id))
            .where(GameResult.group_id == group_id)
            .group_by(GameResult.game_type)
            .order_by(func.count(GameResult.id).desc(), GameResult.game_type)
        )
    ).all()
    leaders = list((await session.scalars(
        select(GamePlayerStats)
        .where(GamePlayerStats.group_id == group_id)
        .order_by(
            GamePlayerStats.rating.desc(),
            GamePlayerStats.wins.desc(),
            GamePlayerStats.games_played.desc(),
        )
        .limit(10)
    )).all())

    lines = [
        "🎮 СТАТИСТИКА ИГР ГРУППЫ",
        "",
        f"🎲 Завершено партий: {completed}",
        f"👥 Игроков со статистикой: {players}",
    ]
    if game_rows:
        lines.extend(["", "По играм:"])
        for game_type, count in game_rows:
            lines.append(f"• {_game_title(game_type)} — {int(count)} партий")
    else:
        lines.extend(["", "Завершённых игровых партий пока нет."])

    if leaders:
        lines.extend(["", "🏆 Топ рейтинга:"])
        for index, row in enumerate(leaders, start=1):
            lines.append(
                f"{index}. {public_user_token(row.user_telegram_id)} — "
                f"⭐ {row.rating} · {row.wins}/{row.games_played} побед"
            )

    lines.extend(["", "В эту статистику входят только полноценные игры, без РП и развлечений."])
    return "\n".join(lines)
