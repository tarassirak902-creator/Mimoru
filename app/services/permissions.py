from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramForbiddenError


async def member_status(bot: Bot, chat_id: int, user_id: int) -> ChatMemberStatus:
    member = await bot.get_chat_member(chat_id, user_id)
    return member.status


async def is_creator(bot: Bot, chat_id: int, user_id: int) -> bool:
    return await member_status(bot, chat_id, user_id) == ChatMemberStatus.CREATOR


async def is_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    return await member_status(bot, chat_id, user_id) in {
        ChatMemberStatus.CREATOR,
        ChatMemberStatus.ADMINISTRATOR,
    }


async def target_is_protected(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        return await is_admin(bot, chat_id, user_id)
    except TelegramForbiddenError:
        # If the bot cannot inspect the target at all, never assume a privileged
        # moderation action is safe. TelegramBadRequest is intentionally left to
        # the caller because panel ban flows allow known users who already left.
        return True
