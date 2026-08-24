from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_legacy_commercial_tables_remain_migratable_for_existing_data():
    models = (ROOT / "app/db/models.py").read_text(encoding="utf-8")
    migration = ROOT / "alembic/versions/0022_commercial_panels_and_ads.py"
    assert "class AdPlacement" in models
    assert "class AdOrder" in models
    assert migration.exists()
    text = migration.read_text(encoding="utf-8")
    assert 'down_revision = "0021_sender_chat_protection"' in text
    assert 'op.create_table("ad_placements"' in text
    assert 'op.create_table("ad_orders"' in text


def test_current_commercial_routers_are_registered_before_catch_all():
    source = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "ad_market_v3.router" in source
    assert "ad_navigation.router" in source
    assert source.index("ad_market_v3.router") < source.index("protection.router")
    assert source.index("ad_navigation.router") < source.index("protection.router")


def test_main_menu_contains_commercial_sections():
    source = (ROOT / "app/keyboards/home.py").read_text(encoding="utf-8")
    for label in ["Управлять моими группами", "Реклама", "Тарифы и подписка"]:
        assert label in source
