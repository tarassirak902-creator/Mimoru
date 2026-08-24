from __future__ import annotations
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
version=(ROOT/'VERSION').read_text().strip()
pyproject=(ROOT/'pyproject.toml').read_text()
m=re.search(r'^version\s*=\s*"([^"]+)"',pyproject,re.M)
if not m: raise SystemExit('pyproject version missing')
pep=m.group(1)
expected=version.replace('-rc','rc')
if pep != expected:
    raise SystemExit(f'Version mismatch: VERSION={version}, pyproject={pep}, expected={expected}')
print(f'Release consistency OK: {version}')
