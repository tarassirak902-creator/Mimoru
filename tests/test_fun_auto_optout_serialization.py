from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_old_auto_game_settings_are_retired() -> None:
    source = (ROOT / "app/handlers/fun_extras.py").read_text(encoding="utf-8")
    assert "async def change_game_settings" not in source
    assert "FunGroupSettings" not in source
    assert "Старые автоматические псевдоигры отключены" in source


def test_old_auto_game_worker_has_no_side_effects() -> None:
    source = (ROOT / "app/tasks_fun.py").read_text(encoding="utf-8")
    assert "select(Group)" not in source
    assert "bot.send_message" not in source
    assert "GameEvent(" not in source
    assert "async def run_fun_auto_activity" in source
    assert "return None" in source


def test_old_auto_game_worker_is_not_started_in_production() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "from app.tasks_fun import fun_background_loop" not in main
    assert "fun-background-loop" not in main
    assert "fun_task" not in main
