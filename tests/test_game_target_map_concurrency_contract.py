from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_target_map_creation_is_serialized_before_shuffle_and_insert() -> None:
    source = (ROOT / "app/games/targets.py").read_text(encoding="utf-8")
    block = source.split("async def ensure_target_map", 1)[1].split("async def resolve_target_number", 1)[0]

    assert "await advisory_xact_lock(" in block
    assert "namespace=_TARGET_MAP_LOCK_NAMESPACE" in block
    assert block.index("await advisory_xact_lock(") < block.index("existing = await get_target_map(")
    assert block.index("existing = await get_target_map(") < block.index("random.SystemRandom().shuffle")
    assert block.index("random.SystemRandom().shuffle") < block.index("session.add_all(rows)")


def test_target_map_race_is_not_recovered_with_integrity_rollback() -> None:
    source = (ROOT / "app/games/targets.py").read_text(encoding="utf-8")
    assert "IntegrityError" not in source
    assert "_TARGET_MAP_LOCK_NAMESPACE" in source
