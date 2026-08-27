from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message


router = Router(name=__name__)
GROUP_TYPES = {"group", "supergroup"}


@router.message(F.chat.type.in_(GROUP_TYPES), F.text.casefold() == "стата игр")
async def game_statistics(message: Message) -> None:
    await message.reply(
        "🎮 Статистика игр\n\n"
        "Новые игры ещё не добавлены, поэтому игровая статистика пока пустая.\n\n"
        "Развлекательные действия, браки, ссоры и отношения больше не считаются играми и сюда не попадают."
    )
