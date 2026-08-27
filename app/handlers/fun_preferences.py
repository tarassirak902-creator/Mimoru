from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app import game_friendly_history, game_friendly_results, group_help_full


router = Router(name=__name__)
GROUP_TYPES = {"group", "supergroup"}
_INCLUDED_CALLBACK_FAMILIES = ("fsfriendly", "fshfriendly")
router.include_router(group_help_full.router)
router.include_router(game_friendly_results.router)
router.include_router(game_friendly_history.router)


@router.message(Command("games"), F.chat.type.in_(GROUP_TYPES))
async def games_command(message: Message) -> None:
    await message.reply(
        "🎮 Игры Mimoru\n\n"
        "Раздел подготовлен для новых полноценных игр. Старые случайные псевдоигры удалены.\n\n"
        "🎭 Развлекательные действия теперь находятся отдельно — напишите «развлечения».\n"
        "💞 Семейные команды и отношения также относятся к развлечениям."
    )
