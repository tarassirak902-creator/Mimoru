from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_rank_policy_mutation_locks_group_before_authorization_and_commit() -> None:
    source = (ROOT / "app/handlers/rank_policy_fix.py").read_text(encoding="utf-8")
    body = source.split("async def rank_policy_permission_fixed(", 1)[1]

    lock = body.index(".with_for_update()")
    owner_check = body.index("group.owner_telegram_id == callback.from_user.id")
    policy_read = body.index("select(GroupRankPolicy)")
    mutation = body.index("custom[permission] =")
    commit = body.index("await session.commit()")

    assert lock < owner_check < policy_read < mutation < commit
    assert "session.get(Group" not in body[:owner_check]
