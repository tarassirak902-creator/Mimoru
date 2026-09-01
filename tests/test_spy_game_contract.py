from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_spy_definition_and_state_machine_contract() -> None:
    source = (ROOT / "app/games/spy/game.py").read_text(encoding="utf-8")

    assert 'code="spy"' in source
    assert 'title="🕵️ Шпион"' in source
    assert "min_players=4" in source
    assert "max_players=8" in source
    assert "exclusive_group_game=True" in source
    assert "supports_rating=True" in source
    assert "uses_private_mapping=True" in source
    assert 'DISCUSSION = "discussion"' in source
    assert 'VOTING = "voting"' in source
    assert 'SPY_GUESS = "spy_guess"' in source
    assert 'FINISHED = "finished"' in source


def test_spy_start_persists_secret_role_and_bounded_location_options() -> None:
    source = (ROOT / "app/games/spy/game.py").read_text(encoding="utf-8")
    start = source.split("async def start", 1)[1].split("async def handle_action", 1)[0]

    assert "LOCATION_OPTIONS_PER_GAME = 8" in source
    assert "rng.choice(LOCATIONS)" in start
    assert "rng.sample(distractors, LOCATION_OPTIONS_PER_GAME - 1)" in start
    assert 'player.role = "spy" if is_spy else "local"' in start
    assert 'player.team = "spy" if is_spy else "locals"' in start
    assert '"location": location' in start
    assert '"location_options": options' in start
    assert '"spy_user_id": spy_player.user_telegram_id' in start
    assert "await session.commit()" in start


def test_spy_vote_and_location_guess_are_phase_guarded() -> None:
    source = (ROOT / "app/games/spy/game.py").read_text(encoding="utf-8")
    resolve = source.split("async def _resolve_vote", 1)[1].split(
        "async def maybe_advance_if_ready", 1
    )[0]
    guess = source.split("async def guess_location", 1)[1].split(
        "async def handle_timeout", 1
    )[0]

    assert "game.phase_seq != expected_phase_seq" in resolve
    assert 'GameAction.action_type == "spy_vote"' in resolve
    assert 'await self._finish(session, game, "spy")' in resolve
    assert "game.phase = SpyPhase.SPY_GUESS.value" in resolve
    assert "actor_telegram_id != state.get(\"spy_user_id\")" in guess
    assert 'GameAction.action_type == "spy_location_guess"' in guess
    assert 'winning_team = "spy" if guessed == state.get("location") else "locals"' in guess


def test_spy_timeouts_and_recovery_are_durable() -> None:
    source = (ROOT / "app/games/spy/game.py").read_text(encoding="utf-8")
    timeout = source.split("async def handle_timeout", 1)[1].split(
        "async def restore", 1
    )[0]
    restore = source.split("async def restore", 1)[1].split("async def sync_ui", 1)[0]

    assert "SpyPhase.DISCUSSION.value" in timeout
    assert "SpyPhase.VOTING.value" in timeout
    assert "SpyPhase.SPY_GUESS.value" in timeout
    assert 'await self._finish(session, game, "locals")' in timeout
    assert 'game.phase == "recovering"' in restore
    assert "has_roles" in restore
    assert "has_state" in restore
    assert "await self.start(session, game)" in restore
    assert "game.deadline_at is None" in restore


def test_spy_finish_uses_durable_game_statistics() -> None:
    source = (ROOT / "app/games/spy/game.py").read_text(encoding="utf-8")
    finish = source.split("async def _finish", 1)[1].split("async def _resolve_vote", 1)[0]

    assert "GameResult(" in finish
    assert "apply_game_result(" in finish
    assert 'player_state.get("result_applied")' in finish
    assert 'player_state["result_applied"] = True' in finish
    assert "rating_enabled=rating_enabled" in finish
