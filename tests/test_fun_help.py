from app.handlers import fun_help


def test_entertainment_help_has_separate_entry_words() -> None:
    assert fun_help.OPEN_WORDS == {"развлечения", "развлекательные команды"}
    assert "игры" not in fun_help.OPEN_WORDS


def test_entertainment_main_menu_has_actions_family_and_close() -> None:
    owner_id = 123456789
    markup = fun_help._main_markup(owner_id)
    callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert callbacks == [
        f"funhelp:{owner_id}:all:0",
        f"funhelp:{owner_id}:family",
        f"funhelp:{owner_id}:close",
    ]


def test_entertainment_back_returns_to_entertainment_home() -> None:
    owner_id = 987654321
    markup = fun_help._back_markup(owner_id)
    callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert f"funhelp:{owner_id}:home" in callbacks
    assert f"funhelp:{owner_id}:close" in callbacks


def test_entertainment_help_explicitly_separates_real_games() -> None:
    text = fun_help._main_text().lower()
    assert "развлекательные команды" in text
    assert "это не игры" in text
    assert "семья и отношения" in text
    assert "/games" in text


def test_plain_actions_exclude_family_proposals() -> None:
    actions = set(fun_help._all_actions())
    family = set(fun_help._family_actions())
    assert actions
    assert "пожениться" not in actions
    assert "пожениться" in family
    assert "выйти замуж" in family
    assert "сделать предложение" in family
    assert "подать на развод" in family
    assert "мои отношения" in family


def test_retired_pseudo_game_categories_are_absent() -> None:
    source = open("app/handlers/fun_help.py", encoding="utf-8").read()
    assert "CATEGORIES" not in source
    assert "🎲 Рандом" not in source
    assert "💰 Криминал" not in source
    assert "Что попробовать?" not in source
