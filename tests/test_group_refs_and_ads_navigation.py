from pathlib import Path

from app.services.plans import PLAN_CATALOG


ROOT = Path(__file__).resolve().parents[1]


def test_required_subscription_limit_is_five_for_every_plan():
    assert {data["limits"]["channels"] for data in PLAN_CATALOG.values()} == {5}


def test_group_reference_resolver_accepts_id_and_username_paths():
    code = (ROOT / "app/services/group_refs.py").read_text(encoding="utf-8")
    assert "Group.telegram_chat_id == number" in code
    assert "Group.id == number" in code
    assert "bot.get_chat(username)" in code
    assert "Group.telegram_chat_id == chat.id" in code


def test_group_lists_expose_id_username_search():
    code = (ROOT / "app/handlers/group_directory.py").read_text(encoding="utf-8")
    assert "group_reference_label" in code
    assert 'callback_data="group_lookup:user"' in code
    assert 'callback_data="group_lookup:service"' in code
    assert "Telegram chat ID" in code


def test_tariff_group_choice_supports_id_username_and_five_required_channels():
    code = (ROOT / "app/handlers/plan_directory.py").read_text(encoding="utf-8")
    assert "до 5 обязательных подписок / каналов" in code
    assert 'callback_data=f"group_lookup:plan:{plan_code}"' in code
    assert "plans_apply" in code
    assert "Группа для подключения: {identity}" in code


def test_advertising_root_matches_current_product_structure():
    code = (ROOT / "app/handlers/ad_navigation.py").read_text(encoding="utf-8")
    for callback in (
        'callback_data="ads:buy"',
        'callback_data="ads:sell"',
        'callback_data="ads:buy:required"',
        'callback_data="ads:buy:post"',
        'callback_data="ads:sell:required"',
    ):
        assert callback in code
    assert "Купить рекламу" in code
    assert "Продать обязательную подписку" in code
    assert "Рекламный пост" in code


def test_current_navigation_routers_precede_catch_all_handlers():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    router_block = main.split("dp.include_routers(", 1)[1]
    routers = [line.strip().rstrip(",") for line in router_block.splitlines() if line.strip().endswith(".router,")]
    assert routers.index("group_directory.router") < routers.index("home_panel.router")
    assert routers.index("plan_catalog.router") < routers.index("navigation.router")
    assert routers.index("ad_market_v3.router") < routers.index("protection.router")
    assert routers.index("group_lookup.router") < routers.index("control_center.router")


def test_ad_marketplace_no_longer_requires_group_lookup_for_buying():
    ads = (ROOT / "app/handlers/ad_market_v3.py").read_text(encoding="utf-8")
    lookup = (ROOT / "app/handlers/group_lookup.py").read_text(encoding="utf-8")
    assert "RequiredAdListing" in ads
    assert 'F.data == "ads:buy:required"' in ads
    assert "ad_required_buy" not in lookup
    assert "ad_required_sell" not in lookup
    assert "ad_post_sell" not in lookup
