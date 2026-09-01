from pathlib import Path

from app.games.mafia.game import MafiaPhase
from app.games.mafia.presentation import _finish_event_lines


ROOT = Path(__file__).resolve().parents[1]


def test_finished_day_keeps_decisive_vote_and_afk_summary() -> None:
    lines = _finish_event_lines({
        "finish_context": {"phase": MafiaPhase.DAY_VOTING.value},
        "last_day_result": {"executed_name": "Алиса", "tie": False},
        "last_afk_removed": ["Борис"],
    })

    assert lines == [
        "Группа выбрала: Алиса покидает игру.",
        "⌛ За повторное бездействие игру покидают: Борис.",
    ]


def test_finished_night_keeps_decisive_night_summary() -> None:
    lines = _finish_event_lines({
        "finish_context": {"phase": MafiaPhase.NIGHT_ACTIONS.value},
        "last_night_result": {"killed_name": "Вера", "saved": False},
        "last_afk_removed": [],
    })

    assert lines == ["Этой ночью погибает Вера."]


def test_winning_resolve_records_context_before_finish_commit() -> None:
    source = (ROOT / "app/games/mafia/game.py").read_text(encoding="utf-8")
    advance = source.split("async def _advance_phase", 1)[1].split("async def handle_timeout", 1)[0]

    assert advance.count("_remember_finish_context(game, current)") == 2
    assert advance.count("await finish_game(session, game, winning_team)") == 2
    first_context = advance.index("_remember_finish_context(game, current)")
    first_finish = advance.index("await finish_game(session, game, winning_team)")
    assert first_context < first_finish
