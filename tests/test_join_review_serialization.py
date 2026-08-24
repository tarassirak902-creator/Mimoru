from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_join_review_locks_group_then_request_before_telegram() -> None:
    code = (ROOT / "app/services/join_review_execution.py").read_text(encoding="utf-8")
    start = code.index("async def execute_join_review")
    body = code[start:]

    group_lock = body.index("select(Group).where(Group.id == group_id).with_for_update()")
    request_lock = body.index("select(JoinRequestRecord)")
    actor_check = body.index("actor_id != group.owner_telegram_id")
    approve_call = body.index("await bot.approve_chat_join_request(")
    decline_call = body.index("await bot.decline_chat_join_request(")
    final_commit = body.rindex("await session.commit()")

    assert group_lock < request_lock < actor_check < approve_call < final_commit
    assert group_lock < request_lock < actor_check < decline_call < final_commit


def test_stale_actor_releases_claim_without_telegram_side_effect() -> None:
    code = (ROOT / "app/services/join_review_execution.py").read_text(encoding="utf-8")
    start = code.index("if actor_id is None or (")
    end = code.index("try:", start)
    stale = code[start:end]

    assert "_reset_review_claim(row)" in stale
    assert "await session.commit()" in stale
    assert 'JoinReviewExecutionResult("stale_actor"' in stale
    assert "approve_chat_join_request" not in stale
    assert "decline_chat_join_request" not in stale


def test_telegram_failure_returns_request_to_pending() -> None:
    code = (ROOT / "app/services/join_review_execution.py").read_text(encoding="utf-8")
    assert "except (TelegramBadRequest, TelegramForbiddenError) as error:" in code
    failure = code[code.index("except (TelegramBadRequest, TelegramForbiddenError) as error:"):]
    assert "_reset_review_claim(row)" in failure
    assert '"telegram_error"' in failure


def test_hardened_join_review_router_wins_before_legacy_router() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert main.index("join_review_guard.router") < main.index("join_requests.router")

    hardened = (ROOT / "app/handlers/join_review_guard.py").read_text(encoding="utf-8")
    legacy = (ROOT / "app/handlers/join_requests.py").read_text(encoding="utf-8")
    for pattern in (
        'F.text.regexp(r"(?i)^одобрить заявку \\d+$")',
        'F.text.regexp(r"(?i)^отклонить заявку \\d+$")',
    ):
        assert pattern in hardened
        assert pattern in legacy
    assert "execute_join_review" in hardened
