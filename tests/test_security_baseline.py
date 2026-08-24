from scripts.check_security_baseline import run_checks


def test_security_baseline() -> None:
    assert run_checks() == []
