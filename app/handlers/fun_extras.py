from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message


router = Router(name=__name__)
GROUP_TYPES = {"group", "supergroup"}


@router.message(F.chat.type.in_(GROUP_TYPES), F.text.casefold().in_({"моя стата игр", "моя игровая стата", "топ игр", "топ игроков"}))
async def empty_game_stats(message: Message) -> None:
    await message.reply(
        "🎮 Новые игры ещё не добавлены. Игровая статистика и рейтинг начнут заполняться после запуска новых игр.\n\n"
        "Старые развлекательные действия и отношения больше не участвуют в игровом рейтинге."
    )


@router.message(F.chat.type.in_(GROUP_TYPES), F.text.casefold().in_({"настройки игр", "авто игры"}))
async def retired_auto_games(message: Message) -> None:
    await message.reply(
        "🎮 Старые автоматические псевдоигры отключены. Настройки настоящих игр появятся вместе с новыми играми."
    )
