from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import game_friendly_history, game_friendly_results, group_help_full
from app.db.fun_models import FunAutoImmunity
from app.db.models import Group
from app.handlers import fun_help


router = Router(name=__name__)
GROUP_TYPES = {"group", "supergroup"}
# Callback families handled by the app-level routers included below. Keeping the
# prefixes declared here lets callback coverage verify their production wiring.
_INCLUDED_CALLBACK_FAMILIES = ("fsfriendly", "fshfriendly")
router.include_router(group_help_full.router)
router.include_router(game_friendly_results.router)
router.include_router(game_friendly_history.router)


@router.message(Command("games"), F.chat.type.in_(GROUP_TYPES))
async def games_command(message: Message) -> None:
    await fun_help.entertainment_help(message)


@router.message(Command("imunitet"), F.chat.type.in_(GROUP_TYPES))
async def toggle_fun_immunity(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return
    group = await session.scalar(
        select(Group)
        .where(
            Group.telegram_chat_id == message.chat.id,
            Group.is_active.is_(True),
        )
        .with_for_update()
    )
    if group is None:
        return

    row = await session.scalar(
        select(FunAutoImmunity).where(
            FunAutoImmunity.group_id == group.id,
            FunAutoImmunity.user_telegram_id == message.from_user.id,
        )
    )
    if row is None:
        row = FunAutoImmunity(
            group_id=group.id,
            user_telegram_id=message.from_user.id,
            enabled=True,
        )
        session.add(row)
        enabled = True
    else:
        row.enabled = not row.enabled
        enabled = row.enabled
    await session.commit()

    if enabled:
        await message.reply(
            "🛡 Игровой иммунитет включён.\n\n"
            "Mimoru больше не будет сама выбирать вас для случайных игровых действий. "
            "Другие участники по-прежнему могут использовать развлечения на вас.\n\n"
            "Чтобы снова разрешить Mimoru взаимодействовать с вами, отправьте /imunitet ещё раз."
        )
    else:
        await message.reply(
            "🎮 Игровой иммунитет выключен.\n\n"
            "Теперь Mimoru снова может случайно выбрать вас для своего игрового действия, "
            "если вы были активны в группе за последнее игровое окно.\n\n"
            "Чтобы снова включить иммунитет, отправьте /imunitet."
        )
