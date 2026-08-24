from pathlib import Path


SOURCE = Path("app/tasks_fun.py").read_text(encoding="utf-8")


def _function_source(name: str) -> str:
    marker = f"async def {name}("
    start = SOURCE.index(marker)
    next_start = SOURCE.find("\n\nasync def ", start + len(marker))
    return SOURCE[start:] if next_start == -1 else SOURCE[start:next_start]


def test_auto_tick_claim_locks_group_and_rechecks_last_tick() -> None:
    claim = _function_source("_claim_auto_tick")

    lock = claim.index(".with_for_update()")
    last_tick = claim.index("last_tick = await session.scalar", lock)
    scan = claim.index('outcome="scan"', last_tick)
    commit = claim.index("await session.commit()", scan)

    assert lock < last_tick < scan < commit
    assert "_group_interval(group_id, interval_code)" in claim


def test_auto_tick_claim_commits_before_any_telegram_send() -> None:
    claim = _function_source("_claim_auto_tick")
    run_claimed = _function_source("_run_claimed_auto_activity")
    runner = _function_source("run_fun_auto_activity")

    assert "await session.commit()" in claim
    assert "bot.send_message" not in claim
    assert "await bot.send_message" in run_claimed
    assert runner.index("await _claim_auto_tick") < runner.index("await _run_claimed_auto_activity")


def test_initial_tick_is_also_committed_under_group_lock() -> None:
    claim = _function_source("_claim_auto_tick")

    init = claim.index('outcome="init"')
    commit = claim.index("await session.commit()", init)
    returned = claim.index("return None", commit)
    assert init < commit < returned


def test_worker_limits_only_successfully_claimed_groups() -> None:
    runner = _function_source("run_fun_auto_activity")

    assert "claimed = 0" in runner
    assert "claimed += 1" in runner
    assert "if claimed >= MAX_GROUPS_PER_TICK" in runner
