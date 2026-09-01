from app.games.handlers import _games_markup
from app.games.registry import game_registry


def test_game_selection_uses_two_buttons_per_row() -> None:
    markup = _games_markup()
    game_rows = markup.inline_keyboard[:-1]
    buttons = [button for row in game_rows for button in row]

    assert len(buttons) == len(game_registry.all())
    assert all(len(row) <= 2 for row in game_rows)
    assert all(button.callback_data.startswith("gm:new:") for button in buttons)


def test_game_selection_keeps_home_button_on_own_row() -> None:
    markup = _games_markup()
    home_row = markup.inline_keyboard[-1]

    assert len(home_row) == 1
    assert home_row[0].callback_data == "gm:home"
