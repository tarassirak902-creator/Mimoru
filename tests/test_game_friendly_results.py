from pathlib import Path

from app import game_friendly_results as friendly


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_friendly_game_routers_are_the_production_social_implementation() -> None:
    preferences = _source("app/handlers/fun_preferences.py")
    social = _source("app/handlers/fun_social.py")
    results = _source("app/game_friendly_results.py")
    history = _source("app/game_friendly_history.py")
    help_source = _source("app/handlers/fun_help.py")

    assert "router.include_router(game_friendly_results.router)" in preferences
    assert "router.include_router(game_friendly_history.router)" in preferences
    assert "@router.message" not in social
    assert "@router.callback_query" not in social
    assert "from app.game_contracts import" in results
    assert "from app.game_contracts import" in history
    assert "from app.game_contracts import PROPOSALS" in help_source


def test_proposal_callback_is_serialized_and_rejects_replay() -> None:
    results = _source("app/game_friendly_results.py")
    callback_block = results.split("async def friendly_answer", 1)[1].split("async def friendly_divorce", 1)[0]
    assert ".with_for_update()" in callback_block
    assert 'GameEvent.outcome == "pending"' in callback_block
    assert '"На это предложение уже ответили."' in callback_block
    assert 'event.outcome = "cancelled"' in callback_block


def test_render_uses_clickable_mentions_without_raw_ids() -> None:
    text, entities = friendly._render(
        "🥊 {actor} победил {target}!",
        {"actor": ("Алексей", 111111111), "target": ("Мария", 222222222)},
    )
    assert text == "🥊 Алексей победил Мария!"
    assert "111111111" not in text
    assert "222222222" not in text
    assert [entity.url for entity in entities] == ["tg://user?id=111111111", "tg://user?id=222222222"]


def test_all_game_actions_have_multiple_short_random_result_variants() -> None:
    assert len(friendly.ACTION_VARIANTS) >= 5
    assert all("{actor}" in item and "{target}" in item for item in friendly.ACTION_VARIANTS)
    assert all(len(item) < 180 for item in friendly.ACTION_VARIANTS)


def test_proposals_and_results_have_multiple_variants_and_emoji() -> None:
    for kind in ("marry", "date", "love", "romance", "duel", "fight"):
        assert len(friendly.PROPOSAL_TEMPLATES[kind]) >= 3
        assert all(any(ord(ch) > 127 for ch in item[:4]) for item in friendly.PROPOSAL_TEMPLATES[kind])
    for kind in ("marry", "date", "love", "romance"):
        assert len(friendly.RESULT_VARIANTS[kind]) >= 3


def test_user_facing_game_text_uses_mentions_not_raw_ids() -> None:
    results = _source("app/game_friendly_results.py")
    history = _source("app/game_friendly_history.py")
    assert "tg://user?id=" in results
    assert "tg://user?id=" in history
    assert "Пользователь {target_id}" not in results
    assert "Победитель: {winner}. Проигравший: {loser}" not in results
    assert "row.user1_telegram_id} ❤️ {row.user2_telegram_id" not in history
