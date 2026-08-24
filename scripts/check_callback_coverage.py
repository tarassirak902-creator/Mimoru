from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
app_files = list((ROOT / "app").rglob("*.py"))
all_text = "\n".join(path.read_text(encoding="utf-8") for path in app_files)
handler_text = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "app/handlers").glob("*.py"))
families: set[str] = set()

for match in re.finditer(r"callback_data\s*=\s*f?[\"']([^\"']+)", all_text):
    raw = match.group(1)
    if not raw:
        continue
    prefix = raw.split(":", 1)[0]
    # Dynamic f-string families such as health_{source}:... cannot be checked
    # reliably by literal text matching; their concrete variants are covered by
    # router-registration and pytest checks instead.
    if "{" in prefix or "}" in prefix:
        continue
    families.add(prefix)

missing = []
for prefix in sorted(families):
    if f"{prefix}:" not in handler_text and f'"{prefix}"' not in handler_text and f"'{prefix}'" not in handler_text:
        missing.append(prefix)

if missing:
    raise SystemExit("Callback families without handlers: " + ", ".join(missing))

print(f"Callback coverage OK: {len(families)} callback families")
