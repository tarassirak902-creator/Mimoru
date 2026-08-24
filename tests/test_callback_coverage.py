import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_all_callback_families_have_handlers():
    all_text = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "app").rglob("*.py"))
    handlers = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "app/handlers").glob("*.py"))
    families = {
        m.group(1).split(":", 1)[0]
        for m in re.finditer(r"callback_data\s*=\s*f?[\"']([^\"']+)", all_text)
        if "{" not in m.group(1).split(":", 1)[0]
    }
    missing = [
        prefix
        for prefix in sorted(families)
        if f"{prefix}:" not in handlers and f'"{prefix}"' not in handlers and f"'{prefix}'" not in handlers
    ]
    assert not missing, missing
