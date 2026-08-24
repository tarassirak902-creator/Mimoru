from datetime import datetime, timedelta, timezone

import pytest

from app.services.edit_protection import normalize_edit_window, should_recheck_edit


def test_recent_edit_is_rechecked():
    now = datetime(2026, 8, 2, 12, tzinfo=timezone.utc)
    original = now - timedelta(hours=1)
    assert should_recheck_edit(original, now, 7200, now=now)


def test_old_edit_is_not_rechecked():
    now = datetime(2026, 8, 2, 12, tzinfo=timezone.utc)
    original = now - timedelta(days=3)
    assert not should_recheck_edit(original, now, 172800, now=now)


def test_edit_window_validation():
    assert normalize_edit_window(300) == 300
    with pytest.raises(ValueError):
        normalize_edit_window(299)
