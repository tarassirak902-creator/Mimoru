from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_private_target_maps_are_actor_and_phase_scoped() -> None:
    source = (ROOT / "app/games/targets.py").read_text(encoding="utf-8")
    models = (ROOT / "app/db/game_models.py").read_text(encoding="utf-8")

    assert "GameTargetMap.game_id == game_id" in source
    assert "GameTargetMap.phase_seq == phase_seq" in source
    assert "GameTargetMap.actor_telegram_id == actor_telegram_id" in source
    assert "random.SystemRandom().shuffle(shuffled)" in source
    assert "target set changed inside active phase" in source
    assert "GameTargetMap.number == number" in source

    assert '"uq_game_target_map_number"' in models
    assert '"uq_game_target_map_target"' in models


def test_private_mapping_never_puts_target_user_id_in_callback_contract() -> None:
    handlers = (ROOT / "app/games/handlers.py").read_text(encoding="utf-8")
    lobby = (ROOT / "app/games/lobby.py").read_text(encoding="utf-8")

    assert "target_telegram_id" not in handlers
    assert "target_telegram_id" not in lobby


def test_numbered_action_is_atomic_and_stale_safe() -> None:
    source = (ROOT / "app/games/actions.py").read_text(encoding="utf-8")

    assert ".with_for_update()" in source
    assert "game.phase_seq != expected_phase_seq" in source
    assert "game.status != GameSessionStatus.RUNNING.value" in source
    assert "actor.status not in {\"joined\", \"alive\"}" in source
    assert "resolve_target_number(" in source
    assert "target.status not in {\"joined\", \"alive\"}" in source
    assert "existing is not None" in source
    assert "return existing, False" in source
    assert "except IntegrityError" in source
    assert 'payload_json={"number": number}' in source


def test_game_action_db_constraint_prevents_double_action_per_phase() -> None:
    migration = (ROOT / "alembic/versions/0046_game_engine_core.py").read_text(encoding="utf-8")
    assert '"uq_game_action_once_per_phase"' in migration
    assert '"game_id", "phase_seq", "actor_telegram_id", "action_type"' in migration
