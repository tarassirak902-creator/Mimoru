from pathlib import Path

from app.handlers.member_profile_v2 import _profile_keyboard


ROOT = Path(__file__).resolve().parents[1]


def _buttons(markup):
    return [button for row in markup.inline_keyboard for button in row]


def test_group_game_stats_command_uses_only_durable_game_stats() -> None:
    handler = (ROOT / "app/handlers/fun_stats.py").read_text(encoding="utf-8")
    views = (ROOT / "app/games/stat_views.py").read_text(encoding="utf-8")

    assert "render_group_game_stats" in handler
    assert "Новые игры ещё не добавлены" not in handler
    assert '"стата игр", "статистика игр"' in handler
    assert "GameResult" in views
    assert "GamePlayerStats" in views
    assert "GamePlayerGameStats" in views
    assert "GameEvent" not in views
    assert "РП и развлечений" in views


def test_profile_games_view_uses_durable_stats_and_rp_is_separate() -> None:
    source = (ROOT / "app/handlers/member_profile_v2.py").read_text(encoding="utf-8")
    games = source.split("async def _games_text", 1)[1].split("async def _rp_text", 1)[0]
    rp = source.split("async def _rp_text", 1)[1].split("async def _view_text", 1)[0]

    assert "render_member_game_stats" in games
    assert "GameEvent" not in games
    assert "GameEvent" in rp
    assert 'RP_EVENT_TYPES = ("action", "entertainment_action", "relationship_action")' in source
    assert "Чаще всего используешь" in rp
    assert "GameMarriage" not in rp


def test_profile_card_has_games_rp_and_close_buttons() -> None:
    markup = _profile_keyboard(group_id=1, target_id=10, requester_id=10, active="profile")
    buttons = _buttons(markup)
    labels = [button.text for button in buttons]
    callbacks = [button.callback_data for button in buttons]

    assert any("🎮 Игры" in label for label in labels)
    assert any("🎭 Мои РП" in label for label in labels)
    assert any("❌ Закрыть" in label for label in labels)
    assert "member_profile_v2:1:10:10:games" in callbacks
    assert "member_profile_v2:1:10:10:rp" in callbacks
    assert "member_profile_v2:1:10:10:close" in callbacks


def test_other_user_profile_does_not_call_rp_view_mine() -> None:
    markup = _profile_keyboard(group_id=1, target_id=20, requester_id=10, active="profile")
    labels = [button.text for button in _buttons(markup)]

    assert any("🎭 РП" in label for label in labels)
    assert all("Мои РП" not in label for label in labels)


def test_close_callback_keeps_requester_guard_before_delete() -> None:
    source = (ROOT / "app/handlers/member_profile_v2.py").read_text(encoding="utf-8")
    callback = source.split("async def profile_tab", 1)[1]

    requester_guard = "if callback.from_user.id != requester_id:"
    delete = "await callback.message.delete()"
    assert '"close"' in callback
    assert requester_guard in callback
    assert delete in callback
    assert callback.index(requester_guard) < callback.index(delete)
