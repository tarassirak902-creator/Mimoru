from app.handlers.group_onboarding_flow import CONNECT_COMMAND, _connect_command_markup


def test_connect_command_button_copies_exact_command() -> None:
    markup = _connect_command_markup()
    assert len(markup.inline_keyboard) == 1
    assert len(markup.inline_keyboard[0]) == 1

    button = markup.inline_keyboard[0][0]
    assert button.text == "📋 подключить"
    assert button.copy_text is not None
    assert button.copy_text.text == CONNECT_COMMAND == "подключить"
    assert button.callback_data is None
    assert button.url is None
