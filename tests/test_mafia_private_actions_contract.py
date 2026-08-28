from pathlib import Path

from app.games.mafia.keyboards import mafia_action_keyboard


ROOT = Path(__file__).resolve().parents[1]


def test_mafia_callback_data_contains_no_target_user_id() -> None:
    markup = mafia_action_keyboard(game_id=123, phase_seq=7, target_count=15)
    callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert "gm:ma:123:7:1" in callbacks
    assert "gm:mm:123:7:1" in callbacks
    assert "gm:mm:123:7:2" in callbacks
    assert all(callback is not None and len(callback.encode()) <= 64 for callback in callbacks)


def test_mafia_private_mapping_is_actor_scoped_and_phase_scoped() -> None:
    source = (ROOT / "app/games/mafia/actions.py").read_text(encoding="utf-8")
    assert "actor_telegram_id=actor_user_id" in source
    assert "phase_seq=game.phase_seq" in source
    assert "ensure_target_map(" in source
    assert "record_numbered_action(" in source


def test_mafia_handlers_reject_stale_phase_and_lock_choice() -> None:
    source = (ROOT / "app/games/mafia/handlers.py").read_text(encoding="utf-8")
    assert "game.phase_seq != phase_seq" in source
    assert "прошлой фазе" in source
    assert "Выбор принят и зафиксирован" in source
    assert "Ваш выбор уже был принят" in source
    assert "text[:200]" in source
