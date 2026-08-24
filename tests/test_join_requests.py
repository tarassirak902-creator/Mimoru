from app.services.join_requests import join_request_status_label, parse_invite_command


def test_parse_normal_invite() -> None:
    result = parse_invite_command("создать ссылку реклама август")
    assert result is not None
    assert result.name == "реклама август"
    assert result.creates_join_request is False


def test_parse_request_invite() -> None:
    result = parse_invite_command("создать ссылку-заявку партнёр")
    assert result is not None
    assert result.creates_join_request is True


def test_status_label() -> None:
    assert join_request_status_label("approved") == "одобрена"
