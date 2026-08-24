from pathlib import Path

from app.services.analytics import PeriodComparison, compact_period_label, report_hour_label, trend_text

ROOT = Path(__file__).resolve().parents[1]


def test_period_comparison_delta_and_percent():
    value = PeriodComparison(120, 100)
    assert value.delta == 20
    assert value.percent == 20.0


def test_period_comparison_zero_baseline():
    assert PeriodComparison(0, 0).percent is None
    assert PeriodComparison(5, 0).percent == 100.0


def test_trend_text_up_down_equal():
    assert trend_text(120, 100) == "↗️ +20%"
    assert trend_text(80, 100) == "↘️ -20%"
    assert trend_text(10, 10) == "без изменений"


def test_period_labels():
    assert compact_period_label(1) == "сегодня"
    assert compact_period_label(7) == "7 дней"
    assert compact_period_label(30) == "30 дней"


def test_report_hour_label():
    assert report_hour_label(6) == "06:00"
    assert report_hour_label(21) == "21:00"


def test_analytics_keyboard_has_all_sections():
    source = (ROOT / "app/keyboards/panel.py").read_text(encoding="utf-8")
    for section in ("activity", "moderation", "growth", "reports"):
        assert f"analytics:{{group_id}}:{section}" in source


def test_dashboard_has_report_controls():
    source = (ROOT / "app/handlers/dashboard.py").read_text(encoding="utf-8")
    assert "analytics_report_toggle" in source
    assert "analytics_report_hour" in source
    assert "previous_totals" in source


def test_daily_report_contains_operational_metrics():
    source = (ROOT / "app/tasks.py").read_text(encoding="utf-8")
    for phrase in ("Новых участников", "Удалено сообщений", "Предупреждений", "Мутов", "Банов"):
        assert phrase in source
