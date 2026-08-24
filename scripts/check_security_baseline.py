from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOTS = (ROOT / "app", ROOT / "scripts", ROOT / "alembic")
TOKEN_RE = re.compile(r"\b\d{5,12}:[A-Za-z0-9_-]{20,}\b")
PRIVATE_KEY_MARKER = "-----BEGIN " + "PRIVATE KEY-----"


def python_files() -> list[Path]:
    files: list[Path] = []
    for root in PYTHON_ROOTS:
        files.extend(root.rglob("*.py"))
    return sorted(files)


def check_ast(path: Path) -> list[str]:
    errors: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = ""
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts: list[str] = []
            current: ast.expr = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            name = ".".join(reversed(parts))
        if name in {"eval", "exec", "os.system"}:
            errors.append(f"{path.relative_to(ROOT)}:{node.lineno}: forbidden call {name}()")
        if name.startswith("subprocess."):
            for keyword in node.keywords:
                if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                    errors.append(f"{path.relative_to(ROOT)}:{node.lineno}: subprocess shell=True is forbidden")
    return errors


def check_text_secrets() -> list[str]:
    errors: list[str] = []
    allowed = {ROOT / ".env.example"}
    excluded_roots = {ROOT / "tests"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.suffix in {".zip", ".pyc"}:
            continue
        if any(root in path.parents for root in excluded_roots):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if path not in allowed and TOKEN_RE.search(text):
            errors.append(f"{path.relative_to(ROOT)}: possible hard-coded Telegram bot token")
        if PRIVATE_KEY_MARKER in text:
            errors.append(f"{path.relative_to(ROOT)}: embedded private key")
    return errors


def check_gitignore() -> list[str]:
    path = ROOT / ".gitignore"
    if not path.exists():
        return [".gitignore is missing"]
    entries = {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")}
    required = {".env", "*.pem", "*.key", "__pycache__/", ".pytest_cache/"}
    missing = sorted(required - entries)
    return [f".gitignore missing security entry: {entry}" for entry in missing]


def run_checks() -> list[str]:
    errors: list[str] = []
    for path in python_files():
        errors.extend(check_ast(path))
    errors.extend(check_text_secrets())
    errors.extend(check_gitignore())
    return errors


def main() -> int:
    errors = run_checks()
    if errors:
        print("Security baseline failed:")
        for error in errors:
            print("-", error)
        return 1
    print("Security baseline OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
