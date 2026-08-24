from __future__ import annotations

from collections.abc import Awaitable, Callable

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group
from app.handlers import group as legacy_group
from app.services.owner_management import managed_group_for_message


router = Router(name=__name__)
GROUP_TYPES = {ChatType.GROUP, ChatType.SUPERGROUP}

OwnerMutation = Callable[[Message, Bot, AsyncSession], Awaitable[None]]


async def _locked_owner_delegate(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    handler: OwnerMutation,
) -> None:
    group = await managed_group_for_message(
        message,
        bot,
        session,
        denial_text="Изменять настройки может только владелец группы.",
        for_update=True,
    )
    if group is None:
        return
    # Keep the Group row lock in this session while the existing production
    # handler performs its dependent reads, mutation, and explicit commit.
    await handler(message, bot, session)


@router.message(
    F.chat.type.in_(GROUP_TYPES),
    F.text.regexp(
        r"(?i)^(?:"
        r"(?:антифлуд|ссылки|капча|приветствие) (?:вкл|выкл)"
        r"|добавить слово .+"
        r"|удалить слово .+"
        r"|добавить подписку @\w+"
        r"|удалить подписку @\w+"
        r")$"
    ),
)
async def serialized_legacy_owner_mutation(
    message: Message,
    bot: Bot,
    session: AsyncSession,
) -> None:
    text = (message.text or "").casefold().strip()
    handler: OwnerMutation
    if text.startswith("антифлуд "):
        handler = legacy_group.toggle_antiflood
    elif text.startswith("ссылки "):
        handler = legacy_group.toggle_links
    elif text.startswith("капча "):
        handler = legacy_group.toggle_captcha
    elif text.startswith("приветствие "):
        handler = legacy_group.toggle_welcome
    elif text.startswith("добавить слово "):
        handler = legacy_group.add_word
    elif text.startswith("удалить слово "):
        handler = legacy_group.remove_word
    elif text.startswith("добавить подписку "):
        handler = legacy_group.add_required_channel
    else:
        handler = legacy_group.remove_required_channel
    await _locked_owner_delegate(message, bot, session, handler)


@router.message(
    F.chat.type.in_(GROUP_TYPES),
    F.reply_to_message,
    F.text.casefold().in_({"удалить", "стереть", "удали"}),
)
async def serialized_legacy_message_delete(
    message: Message,
    bot: Bot,
    session: AsyncSession,
) -> None:
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
    # delete_message_command performs the live rank/owner check itself. Delegating
    # in this session keeps the Group lock across that check, Telegram deletion,
    # moderation-log write, and commit.
    await legacy_group.delete_message_command(message, bot, session)
