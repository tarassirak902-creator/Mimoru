from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_spy_callbacks_validate_game_chat_status_and_phase() -> None:
    source = (ROOT / "app/games/spy/handlers.py").read_text(encoding="utf-8")

    assert 'game.game_type != "spy"' in source
    assert "callback.message.chat.id != group.telegram_chat_id" in source
    assert "game.status != GameSessionStatus.RUNNING.value" in source
    assert "game.phase_seq != phase_seq" in source
    assert "callback.from_user.id" in source


def test_spy_secret_callbacks_only_embed_ids_and_numbers() -> None:
    keyboard = (ROOT / "app/games/spy/keyboards.py").read_text(encoding="utf-8")

    assert 'callback_data=f"gm:sr:{game_id}:{phase_seq}"' in keyboard
    assert 'callback_data=f"gm:svm:{game_id}:{phase_seq}"' in keyboard
    assert 'f"gm:sv:{game_id}:{phase_seq}"' in keyboard
    assert 'callback_data=f"gm:slm:{game_id}:{phase_seq}"' in keyboard
    assert 'f"gm:sl:{game_id}:{phase_seq}"' in keyboard
    assert "target_telegram_id" not in keyboard
    assert "location" not in keyboard.lower().replace("location_count", "")


def test_spy_vote_reuses_common_atomic_action_and_private_mapping() -> None:
    source = (ROOT / "app/games/spy/actions.py").read_text(encoding="utf-8")

    assert "ensure_target_map(" in source
    assert "get_target_map(" in source
    assert "record_numbered_action(" in source
    assert "expected_phase_seq=game.phase_seq" in source
    assert 'action_type="spy_vote"' in source
    assert "GamePlayer.user_telegram_id != actor_user_id" in source
    assert "PRIVATE_NAME_LIMIT = 18" in source


def test_spy_private_data_is_returned_via_callback_popup() -> None:
    source = (ROOT / "app/games/spy/handlers.py").read_text(encoding="utf-8")

    role = source.split("async def spy_private_role", 1)[1].split(
        "async def spy_private_vote_map", 1
    )[0]
    vote_map = source.split("async def spy_private_vote_map", 1)[1].split(
        "async def spy_vote", 1
    )[0]
    location_map = source.split("async def spy_location_map", 1)[1].split(
        "async def spy_location_guess", 1
    )[0]

    assert "callback.answer" in role and "show_alert=True" in role
    assert "callback.answer" in vote_map and "show_alert=True" in vote_map
    assert "callback.answer" in location_map and "show_alert=True" in location_map
    assert "message.answer" not in role + vote_map + location_map


def test_spy_has_server_side_cancel_and_editable_results() -> None:
    source = (ROOT / "app/games/spy/handlers.py").read_text(encoding="utf-8")
    keyboard = (ROOT / "app/games/spy/keyboards.py").read_text(encoding="utf-8")

    assert 'callback_data=f"gm:sc:{game_id}:{phase_seq}"' in keyboard
    assert "async def spy_cancel_running" in source
    assert "await _can_control(" in source
    assert "manager.cancel_game(" in source
    assert "async def spy_results" in source
    assert "callback.message.edit_text" in source
    assert 'callback_data=f"gm:sfinal:{game.id}"' in source
    assert "async def spy_final" in source
