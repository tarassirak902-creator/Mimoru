from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_game_messages_are_reused_and_retired_safely() -> None:
    source = (ROOT / "app/games/messages.py").read_text(encoding="utf-8")

    assert "bot.edit_message_text(" in source
    assert "bot.delete_message(" in source
    assert "message is not modified" in source
    assert "message to delete not found" in source
    assert "TelegramForbiddenError" in source
    assert "current.active = False" in source
    assert "current.retired_at = datetime.now(timezone.utc)" in source
    assert "GameMessage.active.is_(True)" in source


def test_game_statistics_rating_formula_is_isolated() -> None:
    source = (ROOT / "app/games/stats.py").read_text(encoding="utf-8")

    assert "WIN_RATING_DELTA = 20" in source
    assert "LOSS_RATING_DELTA = -10" in source
    assert "def rating_delta(" in source
    assert "async def apply_game_result(" in source
    assert ".with_for_update()" in source
    assert "row.games_played += 1" in source
    assert "row.wins += 1" in source
    assert "row.losses += 1" in source
    assert "group_stats.win_streak += 1" in source
    assert "group_stats.win_streak = 0" in source
    assert "rating_enabled" in source


def test_profiles_and_rating_read_durable_stats() -> None:
    source = (ROOT / "app/games/panels.py").read_text(encoding="utf-8")

    assert "GamePlayerStats" in source
    assert "stats.games_played" in source
    assert "stats.wins" in source
    assert "stats.rating" in source
    assert "stats.win_streak" in source
    assert "GamePlayerStats.rating.desc()" in source
