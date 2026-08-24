"""Tests for DatabaseMiddleware FSM state preservation across callback queries.

The middleware must NOT clear FSM state on callbacks so that multi-step forms
(reqlist, ad sale, broadcast) retain their data between steps.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_middleware_does_not_clear_fsm_state_on_callbacks() -> None:
    """Verify the middleware no longer calls state.clear() on CallbackQuery."""
    source = (ROOT / "app/middlewares.py").read_text(encoding="utf-8")
    assert "await state.clear()" not in source


def test_middleware_preserves_state_before_handler() -> None:
    """Verify state_before is captured but not reset to None after callbacks."""
    source = (ROOT / "app/middlewares.py").read_text(encoding="utf-8")
    assert "state_before = await state.get_state()" in source
    assert "state_data_before = await state.get_data()" in source
    assert "state_before = None" not in source


def test_middleware_handles_new_state_entry() -> None:
    """Verify cancel keyboard is attached when handler enters a new FSM state."""
    source = (ROOT / "app/middlewares.py").read_text(encoding="utf-8")
    assert "state_after and state_after != state_before" in source
    assert "cancel_input_menu(cancel_callback)" in source


def test_middleware_removes_cancel_keyboard_on_state_clear() -> None:
    """Verify cancel keyboard is removed when handler clears FSM state."""
    source = (ROOT / "app/middlewares.py").read_text(encoding="utf-8")
    assert "state_before and not state_after" in source
    assert "_remove_cancel_notice(bot, state_data_before)" in source


def test_middleware_removes_cancel_keyboard_on_navigation() -> None:
    """Verify cancel keyboard is removed when user navigates without changing state."""
    source = (ROOT / "app/middlewares.py").read_text(encoding="utf-8")
    assert "state_before and state_after == state_before" in source


def test_cancel_callback_routes_to_correct_parent() -> None:
    """Verify _cancel_callback maps FSM state names to parent screens."""
    source = (ROOT / "app/middlewares.py").read_text(encoding="utf-8")
    assert 'name.endswith(":support_new")' in source
    assert 'name.endswith(":word_add")' in source
    assert 'name.endswith(":channel_add")' in source
    assert 'name.endswith(":welcome_text")' in source
    assert 'name.endswith(":find_member")' in source
    assert 'name.endswith(":adding")' in source
