from pathlib import Path

from app.games.stats import LOSS_RATING_DELTA, WIN_RATING_DELTA, rating_delta


ROOT = Path(__file__).resolve().parents[1]


def test_rating_delta_contract() -> None:
    assert rating_delta(won=True) == WIN_RATING_DELTA
    assert rating_delta(won=False) == LOSS_RATING_DELTA


def test_stats_creation_is_concurrency_safe_before_row_lock() -> None:
    source = (ROOT / "app/games/stats.py").read_text(encoding="utf-8")
    assert "from sqlalchemy.dialects.postgresql import insert" in source
    assert source.count(".on_conflict_do_nothing(") == 2
    assert 'index_elements=["group_id", "user_telegram_id"]' in source
    assert 'index_elements=["group_id", "user_telegram_id", "game_type"]' in source
    assert source.count(".with_for_update()") == 2


def test_stats_upsert_does_not_swallow_integrity_errors() -> None:
    source = (ROOT / "app/games/stats.py").read_text(encoding="utf-8")
    assert "IntegrityError" not in source
    assert "session.rollback" not in source
