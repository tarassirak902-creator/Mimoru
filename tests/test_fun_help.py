from app.handlers import fun_help


def test_entertainment_help_has_short_entry_words_and_categories():
    assert fun_help.OPEN_WORDS == {"развлечения", "игры"}
    assert {"relations", "family", "fight", "absurd", "crime", "random"} <= set(fun_help.CATEGORIES)


def test_entertainment_main_menu_has_owner_bound_sections_and_categories():
    owner_id = 123456789
    markup = fun_help._main_markup(owner_id)
    callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert f"funhelp:{owner_id}:all:0" in callbacks
    assert f"funhelp:{owner_id}:proposals" in callbacks
    assert f"funhelp:{owner_id}:relations" in callbacks
    assert f"funhelp:{owner_id}:family" in callbacks
    assert f"funhelp:{owner_id}:fight" in callbacks
    assert f"funhelp:{owner_id}:absurd" in callbacks
    assert f"funhelp:{owner_id}:crime" in callbacks
    assert f"funhelp:{owner_id}:random" in callbacks
    assert f"funhelp:{owner_id}:suggest" in callbacks
    assert f"funhelp:{owner_id}:close" in callbacks
    assert all(str(owner_id) in callback for callback in callbacks if callback)


def test_entertainment_category_back_keeps_actions_proposals_and_home_separate():
    owner_id = 987654321
    markup = fun_help._back_markup(owner_id)
    callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert f"funhelp:{owner_id}:all:0" in callbacks
    assert f"funhelp:{owner_id}:proposals" in callbacks
    assert f"funhelp:{owner_id}:home" in callbacks
    assert f"funhelp:{owner_id}:close" in callbacks


def test_entertainment_help_explains_actions_and_proposals_differently():
    text = fun_help._main_text().lower()
    assert "все действия" in text
    assert "срабатывают сразу" in text
    assert "все предложения" in text
    assert "принять или отклонить" in text


def test_all_actions_excludes_social_proposals():
    actions = set(fun_help._all_actions())
    proposals = set(fun_help._proposal_actions())
    assert actions
    assert proposals
    assert actions.isdisjoint(proposals)
    assert "пожениться" in proposals
    assert "пожениться" not in actions


def test_proposals_help_explains_confirmation_and_marriage_commands():
    text = fun_help._proposals_text().lower()
    assert "принять" in text
    assert "отказать" in text
    assert "брак или мой брак" in text
    assert "развестись" in text
