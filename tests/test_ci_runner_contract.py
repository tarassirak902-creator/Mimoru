from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ci_uses_github_hosted_runner_for_public_repo() -> None:
    source = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "runs-on: ubuntu-latest" in source
    assert "self-hosted" not in source
    assert "./scripts/check.sh" in source
