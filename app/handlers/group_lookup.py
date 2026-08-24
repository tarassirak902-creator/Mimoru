from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.access import is_service_owner
from app.services.group_refs import group_reference_label, resolve_group_reference
from app.services.ui import panel_header


router = Router(name=__name__)


class GroupLookupForm(StatesGroup):
    reference = State()


def _return_callback(mode: str, plan_code: str | None = None) -> str:
    if mode == "service":
        return "service:groups"
    if mode == "plan" and plan_code:
        return f"plans_catalog:{plan_code}"
    return "panel:groups"


@router.callback_query(F.data.regexp(r"^group_lookup:(user|service)$"))
async def lookup_start(callback: CallbackQuery, state: FSMContext) -> None:
    mode = callback.data.rsplit(":", 1)[1]
    if mode == "service" and not is_service_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    back = _return_callback(mode)
    await state.set_state(GroupLookupForm.reference)
    await state.update_data(mode=mode, _cancel_callback=back)
    await callback.message.edit_text(
        panel_header(
            "Найти группу",
            "Отправьте Telegram ID уже подключённой группы или её публичный @username.\n\nПримеры:\n-1001234567890\n@my_group",
        )
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^group_lookup:plan:(standard|pro)$"))
async def lookup_plan_start(callback: CallbackQuery, state: FSMContext) -> None:
    plan_code = callback.data.rsplit(":", 1)[1]
    await state.set_state(GroupLookupForm.reference)
    await state.update_data(mode="plan", plan_code=plan_code, _cancel_callback=f"plans_catalog:{plan_code}")
    await callback.message.edit_text(
        panel_header(
            "Найти группу для тарифа",
            f"Тариф: {plan_code.upper()}\n\nОтправьте Telegram ID группы или @username.",
        )
    )
    await callback.answer()


@router.message(GroupLookupForm.reference, F.chat.type == "private")
async def lookup_reference(message: Message, bot: Bot, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    mode = str(data.get("mode") or "user")
    plan_code = data.get("plan_code")
    owner_id = None if mode == "service" and is_service_owner(message.from_user.id) else message.from_user.id
    group = await resolve_group_reference(
        session,
        bot,
        message.text or "",
        owner_telegram_id=owner_id,
        active_only=(mode != "service"),
    )
    if group is None:
        await message.answer(
            "Группа не найдена среди доступных вам групп. Проверьте Telegram ID или @username и отправьте ещё раз."
        )
        return

    label = await group_reference_label(bot, group)
    if mode == "service":
        open_callback = f"service_group:{group.id}"
        back_callback = "service:groups"
        open_text = "🏠 Открыть служебную карточку"
    elif mode == "plan" and plan_code in {"standard", "pro"}:
        open_callback = f"plans_apply:{plan_code}:{group.id}:catalog"
        back_callback = f"plans_catalog:{plan_code}"
        open_text = f"💎 Подключить {str(plan_code).upper()}"
    else:
        open_callback = f"group:{group.id}"
        back_callback = "panel:groups"
        open_text = "🏠 Открыть группу"

    await state.clear()
    await message.answer(
        panel_header("Группа найдена", label),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=open_text, callback_data=open_callback)],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback)],
        ]),
    )
