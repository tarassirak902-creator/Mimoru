from app.handlers.group_onboarding_flow import (
    ADMIN_PROMOTION_RIGHTS,
    _admin_promotion_markup,
)


def test_admin_promotion_button_requests_required_rights() -> None:
    markup = _admin_promotion_markup("MimoruBot")
    assert len(markup.inline_keyboard) == 1
    assert len(markup.inline_keyboard[0]) == 1

    button = markup.inline_keyboard[0][0]
    assert button.text == "🛡 Назначить администратором"
    assert button.url is not None
    assert button.url.startswith("https://t.me/MimoruBot?startgroup=mimoru&admin=")
    for right in ADMIN_PROMOTION_RIGHTS:
        assert right in button.url
    assert button.callback_data is None
    assert button.copy_text is None


def test_admin_promotion_rights_cover_mimoru_group_actions() -> None:
    assert set(ADMIN_PROMOTION_RIGHTS) == {
        "manage_chat",
        "delete_messages",
        "restrict_members",
        "invite_users",
        "pin_messages",
        "promote_members",
    }
