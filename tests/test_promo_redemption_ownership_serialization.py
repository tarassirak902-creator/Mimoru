from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_promo_redemption_locks_current_group_before_promo() -> None:
    source = (ROOT / "app/handlers/client_management.py").read_text(encoding="utf-8")
    body = source.split("async def redeem_promo(", 1)[1].split("@router.message", 1)[0]

    group_lock = body.index("select(Group)")
    owner_filter = body.index("Group.owner_telegram_id == message.from_user.id")
    active_filter = body.index("Group.is_active.is_(True)")
    group_for_update = body.index(".with_for_update()")
    promo_lock = body.index("select(PromoCode)")
    plan_mutation = body.index("group.plan_code = promo.plan_code")
    promo_consumption = body.index("promo.current_uses += 1")
    flush = body.index("await session.flush()")

    assert group_lock < active_filter < group_for_update
    assert group_lock < owner_filter < group_for_update
    assert group_for_update < promo_lock < plan_mutation
    assert plan_mutation < promo_consumption < flush
    assert "session.get(Group" not in body
