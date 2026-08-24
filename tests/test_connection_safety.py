from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_only_explicit_connect_flow_creates_group():
    handlers = ROOT / "app/handlers"
    occurrences: list[tuple[str, int]] = []
    for path in handlers.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        count = source.count("create=True")
        if count:
            occurrences.append((path.name, count))

    assert occurrences == [("group_onboarding_flow.py", 1)]
    source = (handlers / "group_onboarding_flow.py").read_text(encoding="utf-8")
    assert 'F.text.casefold() == "подключить"' in source
    assert "Подключить группу может только её владелец" in source
    assert "is_creator(bot, message.chat.id, message.from_user.id)" in source


def test_repository_refuses_implicit_group_creation():
    source = (ROOT / "app/services/repositories.py").read_text(encoding="utf-8")
    assert "if not create:" in source
    assert "raise GroupNotConnectedError" in source


def test_middleware_handles_unconnected_group_cleanly():
    source = (ROOT / "app/middlewares.py").read_text(encoding="utf-8")
    assert "except GroupNotConnectedError" in source
    assert "Сначала создатель группы должен подключить Mimoru" in source
