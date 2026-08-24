from __future__ import annotations

import structlog
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.models import DailyStat, Group
from app.db.session import SessionFactory
from app.services.deleted_accounts import track_group_member


async def track_outgoing_group_result(method_name: str, result) -> None:
    """Record new group messages sent by Mimoru without affecting delivery.

    Telegram does not send a bot its own outgoing messages as incoming updates,
    so those messages must be accounted for after a successful Bot API send.
    Edit methods are intentionally ignored to avoid inflating activity stats.
    """
    if not method_name.startswith("Send"):
        return
    messages: list[Message]
    if isinstance(result, Message):
        messages = [result]
    elif isinstance(result, list) and all(isinstance(item, Message) for item in result):
        messages = list(result)
    else:
        return

    log = structlog.get_logger()
    for message in messages:
        if message.chat.type not in {"group", "supergroup"} or message.from_user is None:
            continue
        try:
            async with SessionFactory() as session:
                group = await session.scalar(
                    select(Group).where(
                        Group.telegram_chat_id == message.chat.id,
                        Group.is_active.is_(True),
                    )
                )
                if group is None:
                    continue
                await track_group_member(session, group.id, message.from_user, present=True)
                statement = insert(DailyStat).values(
                    group_id=group.id,
                    user_telegram_id=message.from_user.id,
                    date=message.date.date().isoformat(),
                    messages_count=1,
                    deleted_count=0,
                )
                statement = statement.on_conflict_do_update(
                    index_elements=[DailyStat.group_id, DailyStat.user_telegram_id, DailyStat.date],
                    set_={"messages_count": DailyStat.messages_count + 1},
                )
                await session.execute(statement)
                await session.commit()
        except Exception:
            # Activity accounting must never break a successfully delivered Telegram message.
            log.exception(
                "outgoing_activity_tracking_failed",
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                method=method_name,
            )
