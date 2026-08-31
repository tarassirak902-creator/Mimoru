from pathlib import Path
from types import SimpleNamespace

from app.games.mafia.game import MafiaGame
from app.games.mafia.presentation import _day_result_text, _night_result_text
from app.games.mafia.resolution import plurality_target


ROOT = Path(__file__).resolve().parents[1]


def test_minimum_mafia_deck_contains_all_core_roles() -> None:
    roles = MafiaGame._role_deck(4)
    assert len(roles) == 4
    assert roles.count("mafia") == 1
    assert roles.count("doctor") == 1
    assert roles.count("commissioner") == 1
    assert roles.count("civilian") == 1


def test_plurality_requires_unique_winner() -> None:
    assert plurality_target([
        SimpleNamespace(target_telegram_id=10),
        SimpleNamespace(target_telegram_id=10),
        SimpleNamespace(target_telegram_id=20),
    ]) == 10
    assert plurality_target([
        SimpleNamespace(target_telegram_id=10),
        SimpleNamespace(target_telegram_id=20),
    ]) is None
    assert plurality_target([]) is None


def test_public_results_do_not_reveal_secret_roles() -> None:
    day = _day_result_text({"last_day_result": {"executed_name": "Alex", "executed_role": "mafia"}})
    night = _night_result_text({"last_night_result": {"killed_name": "Maria", "killed_role": "doctor"}})
    assert "Alex" in day and "mafia" not in day.casefold()
    assert "Maria" in night and "doctor" not in night.casefold()


def test_mafia_game_contains_victory_afk_and_atomic_finish() -> None:
    game_source = (ROOT / "app/games/mafia/game.py").read_text(encoding="utf-8")
    resolution_source = (ROOT / "app/games/mafia/resolution.py").read_text(encoding="utf-8")
    assert "mafia >= town" in resolution_source
    assert 'mafia == 0' in resolution_source
    assert "player.afk_count >= 2" in game_source
    assert 'player.status = "dead"' in game_source
    assert 'state.get("result_applied")' in resolution_source
    assert "commit=False" in resolution_source


def test_mafia_scheduler_restores_ui_and_expires_lobby() -> None:
    recovery = (ROOT / "app/games/recovery.py").read_text(encoding="utf-8")
    scheduler = (ROOT / "app/tasks_scheduler.py").read_text(encoding="utf-8")
    lobby = (ROOT / "app/games/lobby.py").read_text(encoding="utf-8")
    assert "game_lobby_timeout" in recovery
    assert "recover_active_games(bot)" in scheduler
    assert "process_game_timeouts(bot)" in scheduler
    assert "timedelta(minutes=10)" in lobby


def test_mafia_callbacks_cover_start_role_targets_cancel_and_results() -> None:
    handlers = (ROOT / "app/games/mafia/handlers.py").read_text(encoding="utf-8")
    for prefix in ("gm:ms:", "gm:mr:", "gm:mm:", "gm:ma:", "gm:mc:", "gm:mres:"):
        assert prefix in handlers
    assert "callback.message.chat.id != group.telegram_chat_id" in handlers
    assert "game.phase_seq != phase_seq" in handlers
    assert "can_manage_group" in handlers
