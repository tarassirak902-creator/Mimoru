from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ci_uses_self_hosted_linux_x64_runner() -> None:
    source = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Linux, X64]" in source
    assert "runs-on: ubuntu-latest" not in source
    assert "- run: ./scripts/check.sh" in source
