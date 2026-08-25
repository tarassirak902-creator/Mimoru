"""Tests for DatabaseMiddleware FSM state preservation across callback queries.

The middleware must preserve active multi-step forms while ordinary callbacks
run, but an explicit cancel button must clear the form before navigating back.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_middleware_does_not_clear_fsm_state_on_regular_callbacks() -> None:
    """Only the dedicated cancel notice may clear an active callback form."""
    source = (ROOT / "app/middlewares.py").read_text(encoding="utf-8")
    assert "_callback_is_cancel_notice(event, state_data_before)" in source
    assert "and _callback_is_cancel_notice(event, state_data_before)" in source


def test_middleware_preserves_state_before_handler() -> None:
    """Verify state_before is captured and regular callbacks retain state."""
    source = (ROOT / "app/middlewares.py").read_text(encoding="utf-8")
    assert "state_before = await state.get_state()" in source
    assert "state_data_before = await state.get_data()" in source
    assert "state_before = None" not in source


def test_middleware_handles_new_state_entry() -> None:
    """Verify cancel keyboard is attached when handler enters a new FSM state."""
    source = (ROOT / "app/middlewares.py").read_text(encoding="utf-8")
    assert "state_after and state_after != state_before" in source
    assert "cancel_input_menu(cancel_callback)" in source


def test_cancel_notice_clears_state_before_parent_handler() -> None:
    """Cancel must end the form before the target parent callback is handled."""
    source = (ROOT / "app/middlewares.py").read_text(encoding="utf-8")
    clear_pos = source.index("await state.clear()", source.index("_callback_is_cancel_notice(event, state_data_before)"))
    handler_pos = source.index("result = await handler(event, data)")
    assert clear_pos < handler_pos


def test_middleware_removes_cancel_keyboard_on_state_clear() -> None:
    """Verify cancel keyboard is removed when handler clears FSM state."""
    source = (ROOT / "app/middlewares.py").read_text(encoding="utf-8")
    assert "state_before and not state_after" in source
    assert "_remove_cancel_notice(bot, state_data_before)" in source


def test_middleware_removes_cancel_keyboard_on_navigation() -> None:
    """Verify stale cancel keyboard is removed after regular navigation."""
    source = (ROOT / "app/middlewares.py").read_text(encoding="utf-8")
    assert "state_before and state_after == state_before" in source


def test_cancel_callback_routes_to_correct_parent() -> None:
    """Verify _cancel_callback maps text/photo forms to their logical parent screens."""
    source = (ROOT / "app/middlewares.py").read_text(encoding="utf-8")
    assert 'name.endswith(":support_new")' in source
    assert 'name.endswith(":word_add")' in source
    assert 'name.endswith(":channel_add")' in source
    assert 'name.endswith(":welcome_text")' in source
    assert 'name.endswith(":find_member")' in source
    assert 'name.endswith(":adding")' in source
    assert 'name.startswith("GlobalPostForm:")' in source
    assert 'return f"gpost:editor:{item_id}"' in source
    assert 'name.startswith("RequiredListingForm:")' in source
    assert 'return f"reqlist:group:{group_id}"' in source
    assert 'name.startswith("RequiredDealForm:")' in source
    assert 'return f"reqmarket:{listing_id}"' in source
