from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_old_auto_game_immunity_command_is_removed() -> None:
    preferences = (ROOT / "app/handlers/fun_preferences.py").read_text(encoding="utf-8")
    assert 'Command("imunitet")' not in preferences
    assert "toggle_fun_immunity" not in preferences
    assert "FunAutoImmunity" not in preferences


def test_no_auto_worker_reads_immunity_or_members() -> None:
    tasks = (ROOT / "app/tasks_fun.py").read_text(encoding="utf-8")
    assert "FunAutoImmunity" not in tasks
    assert "GroupMember" not in tasks
    assert "get_chat_member" not in tasks
    assert "send_message" not in tasks


def test_immunity_and_auto_worker_are_not_production_reachable() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "fun_background_loop" not in main
    assert "fun-background-loop" not in main
