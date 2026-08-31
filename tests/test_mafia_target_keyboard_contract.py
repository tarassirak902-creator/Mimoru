from app.games.mafia.keyboards import mafia_action_keyboard


def _callback_data(markup) -> list[str]:
    return [
        button.callback_data or ""
        for row in markup.inline_keyboard
        for button in row
    ]


def test_target_keyboard_does_not_offer_numbers_above_live_bound() -> None:
    markup = mafia_action_keyboard(game_id=10, phase_seq=4, target_count=4)
    callbacks = _callback_data(markup)

    assert "gm:ma:10:4:4" in callbacks
    assert "gm:ma:10:4:5" not in callbacks
    assert "gm:mm:10:4:1" in callbacks
    assert "gm:mm:10:4:2" not in callbacks


def test_target_keyboard_shows_second_map_page_only_when_needed() -> None:
    markup = mafia_action_keyboard(game_id=10, phase_seq=4, target_count=9)
    callbacks = _callback_data(markup)

    assert "gm:ma:10:4:9" in callbacks
    assert "gm:ma:10:4:10" not in callbacks
    assert "gm:mm:10:4:2" in callbacks
