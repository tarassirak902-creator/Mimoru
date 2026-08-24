from types import SimpleNamespace
from app.services.sender_chats import is_group_identity, sender_chat_id

def test_sender_chat_helpers() -> None:
    msg = SimpleNamespace(sender_chat=SimpleNamespace(id=-1001), chat=SimpleNamespace(id=-1001))
    assert sender_chat_id(msg) == -1001
    assert is_group_identity(msg)

def test_sender_chat_missing() -> None:
    msg = SimpleNamespace(sender_chat=None, chat=SimpleNamespace(id=-1001))
    assert sender_chat_id(msg) is None
    assert not is_group_identity(msg)
