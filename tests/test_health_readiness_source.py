from pathlib import Path


def test_health_server_starts_not_ready_and_main_marks_ready_after_get_me():
    health = Path("app/health.py").read_text(encoding="utf-8")
    main = Path("app/main.py").read_text(encoding="utf-8")
    assert "self.ready = False" in health
    start_body = health.split("async def start", 1)[1].split("async def close", 1)[0]
    assert "self.ready = True" not in start_body
    assert main.index("me = await bot.get_me()") < main.index("health.set_ready(True)")
