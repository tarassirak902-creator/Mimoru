from pathlib import Path

from app.keyboards.home import moderation_menu, protection_menu, settings_detail_menu, settings_menu


ROOT = Path(__file__).resolve().parents[1]


def _texts(markup):
    return [button.text for row in markup.inline_keyboard for button in row]


def test_reports_are_not_duplicated_in_group_settings():
    class S:
        welcome_enabled = True
        night_mode_enabled = False
        join_requests_enabled = True

    class G:
        id = 7
        settings = S()

    texts = _texts(settings_menu(G()))
    assert not any("Отчёты" in text for text in texts)
    assert "📝 Приветствие и правила" in texts


def test_antiflood_configuration_lives_in_protection():
    class S:
        antiflood_enabled = True
        repeats_enabled = True
        links_enabled = False
        caps_enabled = True
        captcha_enabled = True
        newcomer_quarantine_enabled = False
        edit_protection_enabled = True
        mention_filter_enabled = False
        sender_chat_filter_enabled = False
        anti_raid_enabled = True

    class G:
        id = 8
        settings = S()

    texts = _texts(protection_menu(G()))
    assert "🌊 Настроить антифлуд" in texts


def test_default_mute_lives_in_moderation():
    texts = _texts(moderation_menu(9))
    assert "🔇 Мут по умолчанию" in texts


def test_settings_detail_contains_only_welcome_and_rules_editor():
    class G:
        id = 10

    texts = _texts(settings_detail_menu(G()))
    assert "✏️ Текст приветствия" in texts
    assert "📜 Правила группы" in texts
    assert not any("Антифлуд" in text or "Мут" in text or "предупреждений" in text for text in texts)


def test_service_clients_do_not_duplicate_paid_and_trial_buttons():
    code = (ROOT / "app/handlers/service_management.py").read_text(encoding="utf-8")
    client_home = code.split("async def _clients_screen", 1)[1].split("@router.callback_query", 1)[0]
    assert 'callback_data="service:clients:paid"' not in client_home
    assert 'callback_data="service:clients:trial"' not in client_home
    assert 'callback_data="service:clients:owners"' in client_home
    assert 'callback_data="service:subscriptions:paid"' in code
    assert 'callback_data="service:subscriptions:trial"' in code


def test_service_group_card_has_live_health_stats_and_contextual_back():
    code = (ROOT / "app/handlers/service_management.py").read_text(encoding="utf-8")
    assert "service_group_health:" in code
    assert "service_group_stats:" in code
    assert "calculate_group_health" in code
    assert '"◀️ К карточке группы"' in code


def test_service_plan_action_fix_precedes_service_management():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "service_management_fixes.router" in main
    assert main.index("service_management_fixes.router") < main.index("service_management.router")
