from pathlib import Path

from app.keyboards.home import service_menu


ROOT = Path(__file__).resolve().parents[1]


def _buttons(markup):
    return [button for row in markup.inline_keyboard for button in row]


def test_service_menu_exposes_group_broadcast_and_back():
    buttons = _buttons(service_menu())
    pairs = {(button.text, button.callback_data) for button in buttons}
    assert ("📣 Рассылка по группам", "service:broadcast") in pairs
    assert ("◀️ Главное меню", "panel:home") in pairs


def test_service_menu_replaces_legacy_menu_before_handlers_import():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "panel_keyboards.service_menu = service_menu" in main
    assert main.index("panel_keyboards.service_menu = service_menu") < main.index("from app.handlers import")


def test_broadcast_composer_has_independent_edit_preview_confirm_and_back_paths():
    code = (ROOT / "app/handlers/service_broadcast.py").read_text(encoding="utf-8")
    for callback in (
        "service:broadcast:text",
        "service:broadcast:photo",
        "service:broadcast:button",
        "service:broadcast:photo_remove",
        "service:broadcast:button_remove",
        "service:broadcast:preview",
        "service:broadcast:confirm",
        "service:broadcast:send",
        "service:broadcast:history",
    ):
        assert callback in code
    assert 'callback_data="service:broadcast"' in code
    assert 'callback_data="service:home"' in code
    assert 'callback_data="service:broadcast:draft"' in code
    assert 'callback_data="service:broadcast:preview"' in code


def test_broadcast_text_photo_and_button_inputs_cancel_back_to_draft():
    code = (ROOT / "app/handlers/service_broadcast.py").read_text(encoding="utf-8")
    assert code.count('_cancel_callback="service:broadcast:draft"') == 3
    assert "class BroadcastForm(StatesGroup)" in code
    for state in ("BroadcastForm.text", "BroadcastForm.photo", "BroadcastForm.button"):
        assert state in code


def test_broadcast_targets_active_groups_not_user_inbox():
    code = (ROOT / "app/handlers/service_broadcast.py").read_text(encoding="utf-8")
    assert "select(Group).where(Group.is_active.is_(True))" in code
    assert "group.telegram_chat_id" in code
    assert "select(User.telegram_id)" not in code


def test_legacy_broadcast_command_is_only_safe_composer_shortcut():
    legacy = (ROOT / "app/handlers/service_admin.py").read_text(encoding="utf-8")
    assert "broadcast_shortcut" in legacy
    assert 'callback_data="service:broadcast"' in legacy
    assert "select(User.telegram_id)" not in legacy
    assert "broadcast_delivery_failed" not in legacy


def test_broadcast_preview_uses_same_renderer_as_delivery():
    code = (ROOT / "app/handlers/service_broadcast.py").read_text(encoding="utf-8")
    assert "async def _send_composed" in code
    assert "await _send_composed(bot, callback.from_user.id, draft)" in code
    assert "await _send_composed(bot, group.telegram_chat_id, payload)" in code
    assert "payload = _payload_snapshot(draft)" in code


def test_broadcast_confirmation_shows_active_group_count():
    code = (ROOT / "app/handlers/service_broadcast.py").read_text(encoding="utf-8")
    assert "select(func.count()).select_from(Group).where(Group.is_active.is_(True))" in code
    assert "Подтвердить и отправить" in code


def test_guided_categories_keep_moved_features_in_expected_parents():
    home = (ROOT / "app/keyboards/home.py").read_text(encoding="utf-8")
    market = (ROOT / "app/handlers/ad_market_v3.py").read_text(encoding="utf-8")
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert 'text="🚫 Запрещённые слова и фразы"' in home
    assert "Обязательная подписка" not in home.split("def content_menu", 1)[1].split("def settings_menu", 1)[0]
    assert 'callback_data=f"channels:{group_id}"' in market
    assert "panel_keyboards.content_menu = content_menu" in main
    assert "panel_keyboards.settings_menu = settings_menu" in main
    assert "panel_keyboards.channels_admin_menu = channels_admin_menu" in main
    assert "panel_keyboards.operations_menu = operations_menu" in main
