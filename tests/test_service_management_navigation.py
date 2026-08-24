from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_visual_service_management_is_registered_before_legacy_dashboard():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    router_block = main.split("dp.include_routers(", 1)[1]
    assert router_block.index("service_management.router") < router_block.index("dashboard.router")
    assert router_block.index("service_admin.router") < router_block.index("dashboard.router")


def test_service_group_tariff_button_has_active_handler_and_back_route():
    management = (ROOT / "app/handlers/service_management.py").read_text(encoding="utf-8")
    admin = (ROOT / "app/handlers/service_admin.py").read_text(encoding="utf-8")
    assert 'callback_data=f"service_plan:{group.id}"' in management
    assert 'r"^service_plan:\\d+$"' in admin or 'r"^service_plan:\\d+$"' in management
    assert 'callback_data=f"service_group:{group.id}"' in admin or 'callback_data=f"service_group:{group.id}"' in management


def test_service_tariff_actions_require_confirmation():
    code = (ROOT / "app/handlers/service_management.py").read_text(encoding="utf-8") + (ROOT / "app/handlers/service_admin.py").read_text(encoding="utf-8")
    assert "service_plan_confirm:" in code
    assert "service_plan_action:" in code or "service_plan_apply:" in code
    assert "✅ Да, подтвердить" in code
    assert "◀️ Отмена" in code


def test_service_client_and_group_actions_are_button_driven_and_subscriptions_are_separate():
    management = (ROOT / "app/handlers/service_management.py").read_text(encoding="utf-8")
    assert "service_client_confirm:" in management
    assert "service_group_confirm:" in management
    assert "service:clients:all" in management
    assert "service:clients:owners" in management
    assert "service:clients:blocked" in management
    assert "service:clients:paid" not in management
    assert "service:clients:trial" not in management
    assert "service:subscriptions:paid" in management
    assert "service:subscriptions:trial" in management
