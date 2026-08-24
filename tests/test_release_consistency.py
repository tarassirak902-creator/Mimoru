import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_release_versions_match():
    version=(ROOT/'VERSION').read_text().strip()
    text=(ROOT/'pyproject.toml').read_text()
    m=re.search(r'^version\s*=\s*"([^"]+)"',text,re.M)
    assert m
    assert m.group(1)==version.replace('-rc','rc')
