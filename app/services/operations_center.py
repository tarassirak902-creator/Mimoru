from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AllowedLink, ForbiddenWord, Group, GroupConfigSnapshot, GroupModerator,
    ModerationReason, OperationEvent, RequiredChannel,
)
from app.services.access import is_service_owner
from app.services.operations_rules import SAFE_SETTING_FIELDS, diagnostics_score


async def record_operation(session: AsyncSession, group_id: int, event_type: str, *, status: str="ok", actor: int|None=None, target: int|None=None, message: str|None=None, details: dict|None=None) -> None:
    session.add(OperationEvent(group_id=group_id,event_type=event_type,status=status,actor_telegram_id=actor,target_telegram_id=target,message=message,details=details))

async def diagnose_group(bot: Bot, group: Group) -> dict[str, Any]:
    result={"reachable":False,"is_admin":False,"delete":False,"restrict":False,"invite":False,"pin":False,"manage_chat":False,"error":None}
    try:
        chat=await bot.get_chat(group.telegram_chat_id)
        me=await bot.get_me()
        member=await bot.get_chat_member(group.telegram_chat_id, me.id)
        result["reachable"]=True
        result["title"]=getattr(chat,"title",None) or group.title
        result["is_admin"]=member.status in {"administrator","creator"}
        result["delete"]=bool(getattr(member,"can_delete_messages",False))
        result["restrict"]=bool(getattr(member,"can_restrict_members",False))
        result["invite"]=bool(getattr(member,"can_invite_users",False))
        result["pin"]=bool(getattr(member,"can_pin_messages",False))
        result["manage_chat"]=bool(getattr(member,"can_manage_chat",False))
    except (TelegramBadRequest, TelegramForbiddenError) as error:
        result["error"]=str(error)[:500]
    return result

async def create_snapshot(session: AsyncSession, group: Group, actor_id: int) -> GroupConfigSnapshot:
    settings={name:getattr(group.settings,name) for name in SAFE_SETTING_FIELDS}
    words=list((await session.scalars(select(ForbiddenWord.word).where(ForbiddenWord.group_id==group.id))).all())
    links=list((await session.scalars(select(AllowedLink.domain).where(AllowedLink.group_id==group.id))).all())
    channels=list((await session.scalars(select(RequiredChannel.channel_username).where(RequiredChannel.group_id==group.id, RequiredChannel.active.is_(True)))).all())
    reasons=(await session.scalars(select(ModerationReason).where(ModerationReason.group_id==group.id).order_by(ModerationReason.sort_order, ModerationReason.id))).all()
    moderators=(await session.scalars(select(GroupModerator).where(GroupModerator.group_id==group.id, GroupModerator.active.is_(True)))).all()
    payload={
        "format":1,"source_group_id":group.id,"source_title":group.title,
        "created_at":datetime.now(timezone.utc).isoformat(),"settings":settings,
        "forbidden_words":words,"allowed_links":links,"required_channels":channels,
        "reasons":[{"name":r.name,"actions":r.actions,"active":r.active,"sort_order":r.sort_order} for r in reasons],
        "moderators":[{"user_telegram_id":m.user_telegram_id,"role":m.role,"permissions":m.permissions} for m in moderators],
    }
    row=GroupConfigSnapshot(group_id=group.id,name=f"{group.title} · {datetime.now(timezone.utc):%d.%m.%Y %H:%M}",payload=payload,created_by_telegram_id=actor_id)
    session.add(row)
    await session.flush()
    await record_operation(session,group.id,"config_snapshot_created",actor=actor_id,details={"snapshot_id":row.id})
    return row

async def apply_snapshot(session: AsyncSession, snapshot: GroupConfigSnapshot, target: Group, actor_id: int) -> None:
    p=snapshot.payload or {}
    for name,value in (p.get("settings") or {}).items():
        if name in SAFE_SETTING_FIELDS:
            setattr(target.settings,name,value)
    await session.execute(delete(ForbiddenWord).where(ForbiddenWord.group_id==target.id))
    await session.execute(delete(AllowedLink).where(AllowedLink.group_id==target.id))
    await session.execute(delete(RequiredChannel).where(RequiredChannel.group_id==target.id))
    await session.execute(delete(ModerationReason).where(ModerationReason.group_id==target.id))
    for word in p.get("forbidden_words") or []:
        session.add(ForbiddenWord(group_id=target.id,word=str(word)[:255]))
    for domain in p.get("allowed_links") or []:
        session.add(AllowedLink(group_id=target.id,domain=str(domain)[:253]))
    for channel in p.get("required_channels") or []:
        session.add(RequiredChannel(group_id=target.id,channel_username=str(channel)[:64],active=True))
    for r in p.get("reasons") or []:
        session.add(ModerationReason(group_id=target.id,name=str(r.get("name","Причина"))[:120],actions=list(r.get("actions") or []),active=bool(r.get("active",True)),sort_order=int(r.get("sort_order",100))))
    # Moderator roles are intentionally not copied automatically: Telegram rights can differ between groups.
    await record_operation(session,target.id,"config_snapshot_applied",actor=actor_id,details={"snapshot_id":snapshot.id,"source_group_id":snapshot.group_id})


async def apply_snapshot_authorized(
    session: AsyncSession,
    *,
    snapshot_id: int,
    target_group_id: int,
    actor_id: int,
) -> Group | None:
    """Revalidate and serialize snapshot restore against current group ownership."""
    snapshot = await session.get(GroupConfigSnapshot, snapshot_id)
    if snapshot is None:
        return None

    group_ids = sorted({snapshot.group_id, target_group_id})
    locked = list((await session.scalars(
        select(Group)
        .where(Group.id.in_(group_ids))
        .order_by(Group.id)
        .with_for_update()
    )).all())
    by_id = {group.id: group for group in locked}
    source = by_id.get(snapshot.group_id)
    target = by_id.get(target_group_id)
    if source is None or target is None or not source.is_active or not target.is_active:
        return None
    if not is_service_owner(actor_id):
        if source.owner_telegram_id != actor_id or target.owner_telegram_id != actor_id:
            return None

    await apply_snapshot(session, snapshot, target, actor_id)
    await session.commit()
    return target
