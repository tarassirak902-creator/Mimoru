from pathlib import Path

from app import game_friendly_results as friendly


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_game_router_runs_before_legacy_fun_handlers() -> None:
    main = _source("app/main.py")
    preferences = _source("app/handlers/fun_preferences.py")
    assert main.index("fun_preferences.router") < main.index("fun_social.router")
    assert main.index("fun_preferences.router") < main.index("fun_commands.router")
    assert "router.include_router(game_friendly_results.router)" in preferences
    assert "router.include_router(game_friendly_history.router)" in preferences


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
    # Numeric IDs are intentionally retained in callback_data and DB lookups. The public renderer
    # must convert identity placeholders to clickable tg:// mentions instead of interpolating them.
    assert "tg://user?id=" in results
    assert "tg://user?id=" in history
    assert "Пользователь {target_id}" not in results
    assert "Победитель: {winner}. Проигравший: {loser}" not in results
    assert "row.user1_telegram_id} ❤️ {row.user2_telegram_id" not in history
