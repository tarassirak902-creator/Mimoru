from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

REQUIRED = ("sqlalchemy", "alembic", "pydantic_settings")
RUNTIME = ("aiogram", "redis", "structlog", "asyncpg")


def check_imports(names: tuple[str, ...]) -> list[str]:
    missing: list[str] = []
    for name in names:
        try:
            importlib.import_module(name)
        except Exception:
            missing.append(name)
    return missing


def run(command: list[str]) -> int:
    print("$", " ".join(command))
    return subprocess.call(command)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    print(f"Repository: {root}")

    missing_required = check_imports(REQUIRED)
    missing_runtime = check_imports(RUNTIME)
    if missing_required:
        print("Missing required local packages:", ", ".join(missing_required))
        return 2
    if missing_runtime:
        print("Runtime packages not installed locally:", ", ".join(missing_runtime))
        print("They are expected to be installed by Docker from pyproject.toml.")

    checks = [
        [sys.executable, "-m", "compileall", "-q", "app", "alembic", "tests"],
        [sys.executable, "-m", "pytest", "-q"],
        [sys.executable, "scripts/check_migrations.py"],
        [sys.executable, "scripts/check_schema_consistency.py"],
        [sys.executable, "scripts/check_router_registration.py"],
        [sys.executable, "scripts/check_deployment_consistency.py"],
        [sys.executable, "scripts/check_security_baseline.py"],
        [sys.executable, "scripts/check_operational_resilience.py"],
        [sys.executable, "scripts/check_functionality_surface.py"],
        [sys.executable, "scripts/check_callback_coverage.py"],
        [sys.executable, "scripts/check_release_consistency.py"],
    ]
    for command in checks:
        if run(command) != 0:
            return 1
    print("Static and unit checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
