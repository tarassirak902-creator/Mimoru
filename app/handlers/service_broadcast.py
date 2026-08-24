from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import structlog
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.broadcast_models import BroadcastDelivery, BroadcastExecution
from app.db.models import Broadcast, Group
from app.keyboards.home import service_menu
from app.services.access import is_service_owner
from app.services.ui import clean_ui_text, panel_header

router = Router(name=__name__)

DRAFT_TTL = 24 * 60 * 60
DELIVERY_CLAIM_STALE_AFTER = timedelta(minutes=10)
UNCERTAIN_DELIVERY_ERROR = "Доставка не подтверждена после прерывания worker; повтор отключён во избежание дубля"


class BroadcastForm(StatesGroup):
    text = State()
    photo = State()
    button = State()


def _key(user_id: int) -> str:
    return f"mimoru:service:broadcast:draft:{user_id}"


def _empty_draft() -> dict[str, Any]:
    return {
        "draft_id": "",
        "text": "",
        "photo_file_id": None,
        "button_text": "",
        "button_url": "",
    }


def _new_draft() -> dict[str, Any]:
    return _empty_draft() | {"draft_id": uuid4().hex}


async def _load(redis: Redis, user_id: int) -> dict[str, Any]:
    raw = await redis.get(_key(user_id))
    if not raw:
        return _empty_draft()
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return _empty_draft()
    defaults = _empty_draft()
    return defaults | {key: data.get(key) for key in defaults}


async def _save(redis: Redis, user_id: int, draft: dict[str, Any]) -> None:
    await redis.setex(_key(user_id), DRAFT_TTL, json.dumps(draft, ensure_ascii=False))


def _request_token(user_id: int, draft: dict[str, Any]) -> str:
    draft_id = str(draft.get("draft_id") or "").strip()
    if draft_id:
        material = f"{user_id}:draft:{draft_id}"
    else:
        legacy_payload = {
            "text": draft.get("text"),
            "photo_file_id": draft.get("photo_file_id"),
            "button_text": draft.get("button_text"),
            "button_url": draft.get("button_url"),
        }
        material = f"{user_id}:legacy:{json.dumps(legacy_payload, ensure_ascii=False, sort_keys=True)}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _payload_snapshot(draft: dict[str, Any]) -> dict[str, Any]:
    return {
        "text": str(draft.get("text") or ""),
        "photo_file_id": draft.get("photo_file_id"),
        "button_text": str(draft.get("button_text") or ""),
        "button_url": str(draft.get("button_url") or ""),
    }


def _editor_keyboard(draft: dict[str, Any]) -> InlineKeyboardMarkup:
    photo_label = "🖼 Изменить изображение" if draft.get("photo_file_id") else "🖼 Добавить изображение"
    text_label = "✏️ Изменить текст" if draft.get("text") else "✏️ Добавить текст"
    button_label = "🔗 Изменить кнопку" if draft.get("button_url") else "🔗 Добавить кнопку"
    rows = [
        [InlineKeyboardButton(text=text_label, callback_data="service:broadcast:text")],
        [InlineKeyboardButton(text=photo_label, callback_data="service:broadcast:photo")],
        [InlineKeyboardButton(text=button_label, callback_data="service:broadcast:button")],
    ]
    if draft.get("photo_file_id"):
        rows.append([InlineKeyboardButton(text="🗑 Удалить изображение", callback_data="service:broadcast:photo_remove")])
    if draft.get("button_url"):
        rows.append([InlineKeyboardButton(text="🗑 Удалить кнопку", callback_data="service:broadcast:button_remove")])
    rows += [
        [InlineKeyboardButton(text="👁 Предпросмотр", callback_data="service:broadcast:preview")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="service:broadcast")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _broadcast_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Новый черновик", callback_data="service:broadcast:new")],
        [InlineKeyboardButton(text="✏️ Продолжить черновик", callback_data="service:broadcast:draft")],
        [InlineKeyboardButton(text="📋 История рассылок", callback_data="service:broadcast:history")],
        [InlineKeyboardButton(text="◀️ Панель Mimoru", callback_data="service:home")],
    ])


def _preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ К подтверждению", callback_data="service:broadcast:confirm")],
        [InlineKeyboardButton(text="✏️ Вернуться к редактированию", callback_data="service:broadcast:draft")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="service:broadcast")],
    ])


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Подтвердить и отправить", callback_data="service:broadcast:send")],
        [InlineKeyboardButton(text="◀️ Назад к предпросмотру", callback_data="service:broadcast:preview")],
    ])


def _url_keyboard(draft: dict[str, Any]) -> InlineKeyboardMarkup | None:
    if not draft.get("button_url"):
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=clean_ui_text(str(draft.get("button_text") or "Открыть"))[:64],
            url=str(draft["button_url"]),
        )
    ]])


def _draft_summary(draft: dict[str, Any]) -> str:
    return panel_header(
        "Рассылка по всем группам",
        "Соберите сообщение по частям. Каждый элемент можно изменить отдельно перед отправкой.",
    ) + (
        f"\n\nТекст: {'✅ добавлен' if draft.get('text') else '— нет'}"
        f"\nИзображение: {'✅ добавлено' if draft.get('photo_file_id') else '— нет'}"
        f"\nКнопка: {'✅ ' + clean_ui_text(str(draft.get('button_text') or 'Открыть')) if draft.get('button_url') else '— нет'}"
    )


async def _send_composed(bot: Bot, chat_id: int, draft: dict[str, Any]) -> None:
    text = clean_ui_text(str(draft.get("text") or ""))
    photo = draft.get("photo_file_id")
    markup = _url_keyboard(draft)
    if photo and text and len(text) <= 1024:
        await bot.send_photo(chat_id, photo, caption=text, reply_markup=markup)
    elif photo:
        await bot.send_photo(chat_id, photo)
        if text:
            await bot.send_message(chat_id, text, reply_markup=markup)
        elif markup:
            await bot.send_message(chat_id, "Открыть ссылку:", reply_markup=markup)
    else:
        await bot.send_message(chat_id, text or "Сообщение Mimoru", reply_markup=markup)


async def _show_editor(callback: CallbackQuery, redis: Redis) -> None:
    draft = await _load(redis, callback.from_user.id)
    await callback.message.edit_text(_draft_summary(draft), reply_markup=_editor_keyboard(draft))
    await callback.answer()


async def _get_or_create_broadcast(
    session: AsyncSession,
    actor_telegram_id: int,
    draft: dict[str, Any],
) -> tuple[Broadcast, dict[str, Any]]:
    token = _request_token(actor_telegram_id, draft)
    execution = await session.scalar(
        select(BroadcastExecution).where(BroadcastExecution.request_token == token).limit(1)
    )
    if execution is not None:
        item = await session.get(Broadcast, execution.broadcast_id)
        if item is None:
            raise RuntimeError("Broadcast execution points to a missing broadcast")
        return item, dict(execution.payload)

    payload = _payload_snapshot(draft)
    item = Broadcast(
        actor_telegram_id=actor_telegram_id,
        text=clean_ui_text(str(payload.get("text") or "[изображение без текста]"))[:4000],
        status="running",
    )
    session.add(item)
    await session.flush()
    session.add(BroadcastExecution(
        request_token=token,
        broadcast_id=item.id,
        payload=payload,
    ))
    try:
        await session.commit()
        return item, payload
    except IntegrityError:
        await session.rollback()
        execution = await session.scalar(
            select(BroadcastExecution).where(BroadcastExecution.request_token == token).limit(1)
        )
        if execution is None:
            raise
        item = await session.get(Broadcast, execution.broadcast_id)
        if item is None:
            raise RuntimeError("Broadcast execution points to a missing broadcast")
        return item, dict(execution.payload)


async def _quarantine_stale_deliveries(
    session: AsyncSession,
    broadcast_id: int,
    now: datetime,
) -> None:
    stale = list((await session.scalars(
        select(BroadcastDelivery).where(
            BroadcastDelivery.broadcast_id == broadcast_id,
            BroadcastDelivery.status == "processing",
            BroadcastDelivery.created_at <= now - DELIVERY_CLAIM_STALE_AFTER,
        )
    )).all())
    for row in stale:
        row.status = "failed"
        row.error_text = UNCERTAIN_DELIVERY_ERROR
        row.finished_at = now
    if stale:
        await session.commit()


async def _claim_delivery(
    session: AsyncSession,
    broadcast_id: int,
    group_id: int,
) -> BroadcastDelivery | None:
    claim = BroadcastDelivery(
        broadcast_id=broadcast_id,
        group_id=group_id,
        status="processing",
    )
    session.add(claim)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await session.scalar(select(BroadcastDelivery.id).where(
            BroadcastDelivery.broadcast_id == broadcast_id,
            BroadcastDelivery.group_id == group_id,
        ).limit(1))
        if existing is not None:
            return None
        raise
    return claim


async def _finalize_broadcast(
    session: AsyncSession,
    item: Broadcast,
    groups: list[Group],
) -> tuple[bool, int, int]:
    deliveries = list((await session.scalars(
        select(BroadcastDelivery).where(BroadcastDelivery.broadcast_id == item.id)
    )).all())
    sent = sum(1 for row in deliveries if row.status == "sent")
    failed = sum(1 for row in deliveries if row.status == "failed")
    active_group_ids = {group.id for group in groups}
    attempted_group_ids = {row.group_id for row in deliveries}
    processing_group_ids = {
        row.group_id for row in deliveries
        if row.status == "processing" and row.group_id in active_group_ids
    }
    completed = active_group_ids.issubset(attempted_group_ids) and not processing_group_ids

    item.sent_count = sent
    item.failed_count = failed
    item.status = "completed" if completed else "running"
    item.finished_at = datetime.now(timezone.utc) if completed else None
    await session.commit()
    return completed, sent, failed


@router.callback_query(F.data == "service:broadcast")
async def broadcast_home(callback: CallbackQuery) -> None:
    if not is_service_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.message.edit_text(
        panel_header(
            "Рассылка по группам",
            "Служебная рассылка владельца Mimoru отправляется во все активные группы, где бот может писать.",
        ),
        reply_markup=_broadcast_home_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "service:broadcast:new")
async def new_draft(callback: CallbackQuery, redis: Redis) -> None:
    if not is_service_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await _save(redis, callback.from_user.id, _new_draft())
    await _show_editor(callback, redis)


@router.callback_query(F.data == "service:broadcast:draft")
async def edit_draft(callback: CallbackQuery, redis: Redis) -> None:
    if not is_service_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await _show_editor(callback, redis)


@router.callback_query(F.data == "service:broadcast:text")
async def request_text(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_service_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await state.set_state(BroadcastForm.text)
    await state.update_data(_cancel_callback="service:broadcast:draft")
    await callback.message.edit_text(panel_header("Текст рассылки", "Отправьте новый текст одним сообщением."))
    await callback.answer()


@router.message(BroadcastForm.text, F.chat.type == "private")
async def save_text(message: Message, state: FSMContext, redis: Redis) -> None:
    if not is_service_owner(message.from_user.id):
        await state.clear(); return
    text = clean_ui_text((message.text or "").strip())[:4000]
    if not text:
        await message.answer("Текст не может быть пустым.")
        return
    draft = await _load(redis, message.from_user.id)
    draft["text"] = text
    await _save(redis, message.from_user.id, draft)
    await state.clear()
    await message.answer(_draft_summary(draft), reply_markup=_editor_keyboard(draft))


@router.callback_query(F.data == "service:broadcast:photo")
async def request_photo(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_service_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True); return
    await state.set_state(BroadcastForm.photo)
    await state.update_data(_cancel_callback="service:broadcast:draft")
    await callback.message.edit_text(panel_header("Изображение рассылки", "Пришлите одно изображение как фото."))
    await callback.answer()


@router.message(BroadcastForm.photo, F.chat.type == "private")
async def save_photo(message: Message, state: FSMContext, redis: Redis) -> None:
    if not is_service_owner(message.from_user.id):
        await state.clear(); return
    if not message.photo:
        await message.answer("Нужно прислать изображение как фото.")
        return
    draft = await _load(redis, message.from_user.id)
    draft["photo_file_id"] = message.photo[-1].file_id
    await _save(redis, message.from_user.id, draft)
    await state.clear()
    await message.answer(_draft_summary(draft), reply_markup=_editor_keyboard(draft))


@router.callback_query(F.data == "service:broadcast:photo_remove")
async def remove_photo(callback: CallbackQuery, redis: Redis) -> None:
    if not is_service_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True); return
    draft = await _load(redis, callback.from_user.id)
    draft["photo_file_id"] = None
    await _save(redis, callback.from_user.id, draft)
    await _show_editor(callback, redis)


@router.callback_query(F.data == "service:broadcast:button")
async def request_button(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_service_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True); return
    await state.set_state(BroadcastForm.button)
    await state.update_data(_cancel_callback="service:broadcast:draft")
    await callback.message.edit_text(
        panel_header("Кнопка рассылки", "Отправьте одной строкой: Название кнопки | https://example.com"),
    )
    await callback.answer()


@router.message(BroadcastForm.button, F.chat.type == "private")
async def save_button(message: Message, state: FSMContext, redis: Redis) -> None:
    if not is_service_owner(message.from_user.id):
        await state.clear(); return
    raw = (message.text or "").strip()
    if "|" not in raw:
        await message.answer("Формат: Название кнопки | https://example.com")
        return
    label, url = (part.strip() for part in raw.split("|", 1))
    if not label or not url.startswith(("https://", "http://", "tg://")):
        await message.answer("Проверьте название и ссылку. Ссылка должна начинаться с https://, http:// или tg://")
        return
    draft = await _load(redis, message.from_user.id)
    draft["button_text"] = clean_ui_text(label)[:64]
    draft["button_url"] = url[:512]
    await _save(redis, message.from_user.id, draft)
    await state.clear()
    await message.answer(_draft_summary(draft), reply_markup=_editor_keyboard(draft))


@router.callback_query(F.data == "service:broadcast:button_remove")
async def remove_button(callback: CallbackQuery, redis: Redis) -> None:
    if not is_service_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True); return
    draft = await _load(redis, callback.from_user.id)
    draft["button_text"] = ""
    draft["button_url"] = ""
    await _save(redis, callback.from_user.id, draft)
    await _show_editor(callback, redis)


@router.callback_query(F.data == "service:broadcast:preview")
async def preview(callback: CallbackQuery, bot: Bot, redis: Redis) -> None:
    if not is_service_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True); return
    draft = await _load(redis, callback.from_user.id)
    if not draft.get("text") and not draft.get("photo_file_id"):
        await callback.answer("Добавьте текст или изображение.", show_alert=True)
        return
    await _send_composed(bot, callback.from_user.id, draft)
    await callback.message.edit_text(
        panel_header("Предпросмотр готов", "Выше сообщение показано так, как оно будет отправлено в группы. Проверьте каждую деталь."),
        reply_markup=_preview_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "service:broadcast:confirm")
async def confirm(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not is_service_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True); return
    draft = await _load(redis, callback.from_user.id)
    if not draft.get("text") and not draft.get("photo_file_id"):
        await callback.answer("Черновик пуст.", show_alert=True); return
    count = int(await session.scalar(select(func.count()).select_from(Group).where(Group.is_active.is_(True))) or 0)
    await callback.message.edit_text(
        panel_header(
            "Подтверждение рассылки",
            f"Сообщение будет отправлено в {count} активных групп. Ошибка одной группы не остановит остальные.",
        ),
        reply_markup=_confirm_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "service:broadcast:send")
async def send_broadcast(callback: CallbackQuery, bot: Bot, session: AsyncSession, redis: Redis) -> None:
    if not is_service_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True); return
    draft = await _load(redis, callback.from_user.id)
    if not draft.get("text") and not draft.get("photo_file_id"):
        await callback.answer("Черновик пуст.", show_alert=True); return

    item, payload = await _get_or_create_broadcast(session, callback.from_user.id, draft)
    if item.status == "completed":
        await redis.delete(_key(callback.from_user.id))
        await callback.message.edit_text(
            panel_header(
                "Рассылка уже завершена",
                f"Доставлено в групп: {item.sent_count}\nОшибок: {item.failed_count}",
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 История рассылок", callback_data="service:broadcast:history")],
                [InlineKeyboardButton(text="◀️ Панель Mimoru", callback_data="service:home")],
            ]),
        )
        await callback.answer("Уже выполнено")
        return

    await _quarantine_stale_deliveries(session, item.id, datetime.now(timezone.utc))
    groups = list((await session.scalars(
        select(Group).where(Group.is_active.is_(True)).order_by(Group.id)
    )).all())
    await callback.message.edit_text(
        panel_header(
            "Рассылка запущена",
            f"Групп в текущем снимке: {len(groups)}. Повторный запуск безопасно продолжит только необработанные группы.",
        )
    )

    log = structlog.get_logger()
    for group in groups:
        claim = await _claim_delivery(session, item.id, group.id)
        if claim is None:
            continue

        status = "sent"
        error_text: str | None = None
        try:
            while True:
                try:
                    await _send_composed(bot, group.telegram_chat_id, payload)
                    break
                except TelegramRetryAfter as exc:
                    await asyncio.sleep(float(exc.retry_after) + 0.2)
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            status = "failed"
            error_text = str(exc)[:1000]
            log.warning(
                "group_broadcast_delivery_failed",
                broadcast_id=item.id,
                group_id=group.id,
                chat_id=group.telegram_chat_id,
                error=str(exc),
            )
        except Exception as exc:
            status = "failed"
            error_text = str(exc)[:1000]
            log.exception(
                "group_broadcast_delivery_failed",
                broadcast_id=item.id,
                group_id=group.id,
                chat_id=group.telegram_chat_id,
                error=str(exc),
            )

        claim.status = status
        claim.error_text = error_text
        claim.finished_at = datetime.now(timezone.utc)
        await session.commit()
        await asyncio.sleep(0.05)

    completed, sent, failed = await _finalize_broadcast(session, item, groups)
    if completed:
        await redis.delete(_key(callback.from_user.id))
        await callback.message.edit_text(
            panel_header("Рассылка завершена", f"Доставлено в групп: {sent}\nОшибок: {failed}"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 История рассылок", callback_data="service:broadcast:history")],
                [InlineKeyboardButton(text="◀️ Панель Mimoru", callback_data="service:home")],
            ]),
        )
        await callback.answer("Готово")
        return

    await callback.message.edit_text(
        panel_header(
            "Рассылка ещё выполняется",
            f"Подтверждено доставок: {sent}\nОшибок: {failed}\n\nЕсть активные или неопределённые claims. Повторите отправку позже: уже обработанные группы будут пропущены.",
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Продолжить", callback_data="service:broadcast:send")],
            [InlineKeyboardButton(text="📋 История рассылок", callback_data="service:broadcast:history")],
        ]),
    )
    await callback.answer("Состояние сохранено")


@router.callback_query(F.data == "service:broadcast:history")
async def history(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_service_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True); return
    rows = (await session.scalars(select(Broadcast).order_by(Broadcast.created_at.desc()).limit(15))).all()
    lines = []
    for row in rows:
        date = row.created_at.strftime("%d.%m.%Y %H:%M") if row.created_at else "—"
        lines.append(f"• #{row.id} · {date} · {row.status} · ✅ {row.sent_count} / ❌ {row.failed_count}")
    await callback.message.edit_text(
        panel_header("История рассылок", "Последние запуски по группам") + "\n\n" + ("\n".join(lines) if lines else "Рассылок пока нет."),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад к рассылкам", callback_data="service:broadcast")],
            [InlineKeyboardButton(text="◀️ Панель Mimoru", callback_data="service:home")],
        ]),
    )
    await callback.answer()
