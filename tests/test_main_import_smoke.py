import os
import subprocess
import sys


def test_application_main_imports() -> None:
    env = os.environ.copy()
    env.setdefault("BOT_TOKEN", "123456:abcdefghijklmnopqrstuvwxyz123456")
    result = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
