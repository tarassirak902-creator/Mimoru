from types import SimpleNamespace
from app.services.audit_format import render_log

def test_render_log_contains_ids():
    group = SimpleNamespace(title="Тест")
    row = SimpleNamespace(action="mute", actor_telegram_id=10, target_telegram_id=20, reason="флуд", id=7)
    text = render_log(group, row)
    assert "Мут" in text
    assert "10" in text and "20" in text
    assert "LOG-7" in text
