import asyncio
from typing import Any

import structlog
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import TelegramMethod
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import DatabaseMiddleware, dispose_engine
from app.handlers import ad_invoice_safety, ad_legacy_payment_guard, ad_market_atomic, ad_market_v3, ad_navigation, admin_access_mode, advanced, audit, automation, billing, campaign_spam, client_management, common, contextual_back, control_center, deferred_bans, deleted_accounts, member_center, member_navigation, dashboard, edit_protection, features, fun_bot_guard, fun_commands, fun_extras, fun_help, fun_preferences, fun_social, fun_stats, group, group_action_aliases, group_commands, group_directory, group_lookup, group_onboarding_flow, group_owner_mutation_fixes, group_shortcuts, group_stats_v2, hardening, home_panel, input_safety, invite_operation_guard, join_review_guard, join_requests, member_profile_v2, members, mentions, moderation_command_modes, moderation_durable_guard, navigation, navigation_fixes, operations, operations_center, onboarding, panel, permission_modes, plan_catalog, plan_directory, plan_legacy_redirect, protection, quarantine, rank_legacy_guard, rank_policy_fix, rank_provisioning_handlers, rank_text_commands, reason_admin, required_direct, safety, service_admin, service_broadcast, service_group_access, service_management, service_management_fixes, service_owner_directory, setup_legacy_redirect, slow_mode, sender_chats, mimoru_identity, telegram_roles, wizard_navigation, kick_retirement
from app.health import HealthServer
from app.middlewares import CancelledReplyMiddleware
from app.middlewares_rank_access import RankAccessModeMiddleware
from app.preflight import run_preflight
from app.services.ad_market_schema import ensure_ad_market_schema
from app.services.background_leader import leader_background_loop
from app.services.chat_permission_transitions import ensure_chat_permission_transition_schema
from app.services.deleted_accounts import ensure_deleted_cleanup_retry_schema
from app.services.group_disconnects import ensure_group_disconnect_schema
from app.services.invite_execution import ensure_invite_operation_schema
from app.services.moderation_operation_schema import ensure_moderation_operation_schema
from app.services.moderation_operations import recover_moderation_operation_intents
from app.services.rank_provisioning import ensure_rank_provisioning_schema
from app.services.required_resources import ensure_required_resource_schema
from app.services.runtime import configure_runtime
from app.services.ui import clean_ui_text
from app.services.user_refs import replace_public_group_id_labels


_IDEMPOTENT_EDIT_METHODS = {"EditMessageText", "EditMessageReplyMarkup", "EditMessageCaption", "EditMessageMedia"}


def _plain_reply_markup(markup: Any) -> Any:
    if markup is None or not hasattr(markup, "inline_keyboard"):
        return markup
    rows = []
    changed = False
    for row in markup.inline_keyboard:
        new_row = []
        for button in row:
            text = clean_ui_text(button.text) if isinstance(button.text, str) else button.text
            if text != button.text:
                changed = True
                button = button.model_copy(update={"text": text})
            new_row.append(button)
        rows.append(new_row)
    return markup.model_copy(update={"inline_keyboard": rows}) if changed else markup


def _plain_method(method: TelegramMethod[Any]) -> TelegramMethod[Any]:
    updates: dict[str, Any] = {}
    for field in ("text", "caption"):
        value = getattr(method, field, None)
        if isinstance(value, str):
            updates[field] = clean_ui_text(value)
    reply_markup = getattr(method, "reply_markup", None)
    if reply_markup is not None:
        updates["reply_markup"] = _plain_reply_markup(reply_markup)
    if hasattr(method, "parse_mode"):
        updates["parse_mode"] = None
    if hasattr(method, "caption_parse_mode"):
        updates["caption_parse_mode"] = None
    return method.model_copy(update=updates) if updates else method


def _is_idempotent_edit_error(method: TelegramMethod[Any], exc: TelegramBadRequest) -> bool:
    return (
        type(method).__name__ in _IDEMPOTENT_EDIT_METHODS
        and "message is not modified" in str(exc).casefold()
    )


def _disable_legacy_direct_moderation_handlers() -> None:
    """Keep пред/мут/бан on one message-handler path only.

    Several older routers can consume the same reply command and always open the
    legacy reason picker. They remain importable for helpers/callbacks, but their
    competing message entrypoints are removed at startup. All unrelated handlers
    and callbacks stay registered.
    """
    retired = {
        id(kick_retirement.router): {"moderation_reason_entry"},
        id(group_commands.router): {"direct_reply_moderation"},
        id(moderation_durable_guard.router): {"durable_direct_reply"},
    }
    for legacy_router in (
        kick_retirement.router,
        group_commands.router,
        moderation_durable_guard.router,
    ):
        names = retired[id(legacy_router)]
        legacy_router.message.handlers[:] = [
            handler
            for handler in legacy_router.message.handlers
            if getattr(handler.callback, "__name__", "") not in names
        ]


class PlainTextBot(Bot):
    async def __call__(self, method: TelegramMethod[Any], request_timeout: int | None = None) -> Any:
        plain_method = _plain_method(method)
        plain_method = await replace_public_group_id_labels(self, plain_method)
        try:
            result = await super().__call__(plain_method, request_timeout=request_timeout)
        except TelegramBadRequest as exc:
            if _is_idempotent_edit_error(plain_method, exc):
                return True
            raise
        await track_outgoing_group_result(type(plain_method).__name__, result)
        return result

    async def send_message(self, *args, **kwargs):
        text = kwargs.get("text")
        if text is None and len(args) >= 2 and isinstance(args[1], str):
            mutable = list(args)
            mutable[1] = clean_ui_text(args[1])
            args = tuple(mutable)
        elif isinstance(text, str):
            kwargs["text"] = clean_ui_text(text)
        kwargs.pop("parse_mode", None)
        return await super().send_message(*args, **kwargs)

    async def edit_message_text(self, *args, **kwargs):
        text = kwargs.get("text")
        if text is None and args and isinstance(args[0], str):
            mutable = list(args)
            mutable[0] = clean_ui_text(args[0])
            args = tuple(mutable)
        elif isinstance(text, str):
            kwargs["text"] = clean_ui_text(text)
        kwargs.pop("parse_mode", None)
        return await super().edit_message_text(*args, **kwargs)


async def configure_bot(bot: Bot) -> None:
    await bot.set_my_commands([
        BotCommand(command="start", description="Открыть главное меню"),
        BotCommand(command="help", description="Помощь по боту Mimoru"),
    ])
    await bot.set_my_commands([
        BotCommand(command="games", description="Развлечения"),
        BotCommand(command="report", description="Пожаловаться"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="comands", description="Список команд"),
        BotCommand(command="oftop", description="Связь с владельцем бота"),
    ], scope=BotCommandScopeAllGroupChats())
    await bot.delete_webhook(drop_pending_updates=False)


async def main() -> None:
    configure_logging()
    log = structlog.get_logger()
    settings = get_settings()
    bot = PlainTextBot(settings.bot_token)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    health = HealthServer(redis, settings.health_host, settings.health_port)
    dp = Dispatcher(redis=redis)
    cancelled_reply_middleware = CancelledReplyMiddleware(redis)
    db_middleware = DatabaseMiddleware()
    rank_access_middleware = RankAccessModeMiddleware()
    dp.message.outer_middleware(cancelled_reply_middleware)
    dp.message.outer_middleware(db_middleware)
    dp.edited_message.outer_middleware(db_middleware)
    dp.callback_query.outer_middleware(db_middleware)
    dp.pre_checkout_query.outer_middleware(db_middleware)
    dp.chat_join_request.outer_middleware(db_middleware)
    dp.chat_member.outer_middleware(db_middleware)
    dp.my_chat_member.outer_middleware(db_middleware)
    for rank_router in (admin_access_mode.router, telegram_roles.router):
        rank_router.callback_query.middleware(rank_access_middleware)
        rank_router.message.middleware(rank_access_middleware)
    _disable_legacy_direct_moderation_handlers()
    dp.include_routers(
        fun_preferences.router,
        fun_extras.router,
        group_onboarding_flow.router,
        mimoru_identity.router,
        member_profile_v2.router,
        group_stats_v2.router,
        deferred_bans.router,
        rank_provisioning_handlers.router,
        rank_text_commands.router,
        group_action_aliases.router,
        group_shortcuts.router,
        common.router,
        group_lookup.router,
        member_navigation.router,
        service_owner_directory.router,
        contextual_back.router,
        group_directory.router,
        plan_directory.router,
        ad_invoice_safety.router,
        ad_market_atomic.router,
        ad_market_v3.router,
        ad_navigation.router,
        home_panel.router,
        plan_catalog.router,
        plan_legacy_redirect.router,
        navigation.router,
        wizard_navigation.router,
        setup_legacy_redirect.router,
        navigation_fixes.router,
        input_safety.router,
        automation.router,
        operations_center.router,
        ad_legacy_payment_guard.router,
        billing.router,
        kick_retirement.router,
        moderation_command_modes.router,
        moderation_durable_guard.router,
        reason_admin.router,
        group_commands.router,
        fun_help.router,
        fun_bot_guard.router,
        fun_stats.router,
        fun_social.router,
        fun_commands.router,
        rank_legacy_guard.router,
        rank_policy_fix.router,
        admin_access_mode.router,
        telegram_roles.router,
        control_center.router,
        onboarding.router,
        deleted_accounts.router,
        member_center.router,
        panel.router,
        service_management_fixes.router,
        service_group_access.router,
        service_management.router,
        service_admin.router,
        service_broadcast.router,
        client_management.router,
        campaign_spam.router,
        hardening.router,
        safety.router,
        required_direct.router,
        sender_chats.router,
        slow_mode.router,
        permission_modes.router,
        protection.router,
        quarantine.router,
        mentions.router,
        edit_protection.router,
        invite_operation_guard.router,
        join_review_guard.router,
        join_requests.router,
        group_owner_mutation_fixes.router,
        advanced.router,
        features.router,
        audit.router,
        dashboard.router,
        operations.router,
        group.router,
        members.router,
    )

    await configure_runtime(redis)
    await ensure_required_resource_schema()
    await ensure_moderation_operation_schema()
    await ensure_rank_provisioning_schema()
    await ensure_chat_permission_transition_schema()
    await ensure_invite_operation_schema()
    await ensure_deleted_cleanup_retry_schema()
    await ensure_group_disconnect_schema()
    await ensure_ad_market_schema()
    await recover_moderation_operation_intents(bot)
    await run_preflight(bot, redis)
    await configure_bot(bot)
    await health.start()
    leader_task = asyncio.create_task(leader_background_loop(bot, redis))
    log.info("bot_started", bot_id=bot.id, username=(await bot.get_me()).username)
    try:
        await dp.start_polling(bot)
    finally:
        leader_task.cancel()
        await health.stop()
        await dispose_engine()
        await redis.aclose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
