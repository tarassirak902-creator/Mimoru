from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from redis.asyncio import Redis

from app.keyboards.home import HOME_HINT, home_menu
from app.reply_safety import CANCELLED_REPLY_KEY
from app.services.access import is_service_owner
from app.services.ui import panel_header


router = Router(name=__name__)


@router.callback_query(F.data.regexp(r"^reply_cancel:\d+$"))
async def cancel_force_reply(callback: CallbackQuery, bot: Bot, redis: Redis) -> None:
    """Cancel the exact ForceReply prompt and remember it if deletion is unavailable."""
    prompt_message_id = int(callback.data.split(":", 1)[1])
    key = CANCELLED_REPLY_KEY.format(
        user_id=callback.from_user.id,
        message_id=prompt_message_id,
    )
    # Keep the marker long enough that an old cancelled prompt cannot become
    # active again merely because Telegram no longer allows message deletion.
    await redis.setex(key, 365 * 24 * 60 * 60, "1")
    if callback.message is not None:
        try:
            await bot.delete_message(callback.message.chat.id, prompt_message_id)
        except TelegramBadRequest:
            pass
        await callback.message.edit_text(
            panel_header(
                "Ввод отменён",
                "Ничего не сохранено.\n\n" + HOME_HINT,
            ),
            reply_markup=home_menu(is_service_owner(callback.from_user.id)),
        )
    await callback.answer("Ввод отменён")
