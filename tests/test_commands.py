from app.utils.commands import parse_command


def test_mute_with_duration_and_reason():
    cmd = parse_command("Мут 2ч флуд")
    assert cmd and cmd.action == "mute" and cmd.duration == 7200 and cmd.reason == "флуд"


def test_warn():
    cmd = parse_command("пред реклама")
    assert cmd and cmd.action == "warn" and cmd.reason == "реклама"


def test_unknown():
    assert parse_command("обычное сообщение") is None


def test_multiword_unwarn():
    cmd = parse_command("снять пред ошибочная выдача")
    assert cmd and cmd.action == "unwarn" and cmd.reason == "ошибочная выдача"


def test_history():
    cmd = parse_command("история")
    assert cmd and cmd.action == "history"


def test_retired_kick_aliases_are_not_commands():
    for text in ["кик", "кик флуд", "выгнать", "выгнать за спам"]:
        assert parse_command(text) is None
