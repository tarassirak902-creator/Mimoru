from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_moderation_intent_schema_is_durable_and_unique_per_target() -> None:
    model = _source("app/db/moderation_operation_models.py")
    schema = _source("app/services/moderation_operation_schema.py")
    assert "ModerationOperationIntent" in model
    assert '"group_id"' in model and '"target_telegram_id"' in model
    assert "uq_moderation_operation_group_target" in model
    assert "payload: Mapped[dict]" in model
    assert "ModerationOperationIntent.__table__.create" in schema
    assert "checkfirst=True" in schema


def test_guard_keeps_non_conflicting_production_entries_and_direct_commands_are_removed() -> None:
    main = _source("app/main.py")
    guard = _source("app/handlers/moderation_durable_guard.py")
    group_commands = _source("app/handlers/group_commands.py")
    kick_retirement = _source("app/handlers/kick_retirement.py")

    assert "_disable_legacy_direct_moderation_handlers" not in main
    assert "async def durable_direct_reply" not in guard
    assert "async def direct_reply_moderation" not in group_commands
    assert "async def moderation_reason_entry" not in kick_retirement

    assert r"^modreason:[0-9a-f]{10}:\d+$" in guard
    assert 'F.text.casefold() == "говори"' in guard
    assert 'F.text.casefold().startswith("разбан ")' in guard
    assert r"^member_action:\d+:-?\d+:(unmute|unban)$" in guard


def test_guard_authorizes_and_snapshots_before_committing_mutation_intent() -> None:
    guard = _source("app/handlers/moderation_durable_guard.py")
    assert "async def _telegram_snapshot" in guard
    assert '"pre_banned"' in guard
    assert '"pre_muted"' in guard
    assert '"pre_until"' in guard
    assert "async def _authorized_for_action" in guard
    assert "await can_moderate(" in guard
    assert "await can_moderate_target(" in guard

    reason = guard.split("async def durable_reason_action", 1)[1].split(
        "async def durable_reply_unmute", 1
    )[0]
    assert reason.index("await _authorized_for_action(") < reason.index(
        "await _create_guard_intent("
    )
    assert reason.index("await _telegram_snapshot(") < reason.index(
        "await _create_guard_intent("
    )
    assert "reason.active" in reason and "normalize_actions(reason.actions)" in reason


def test_guard_commits_intent_before_delegating_existing_hardened_logic() -> None:
    guard = _source("app/handlers/moderation_durable_guard.py")
    reason = guard.split("async def durable_reason_action", 1)[1].split(
        "async def durable_reply_unmute", 1
    )[0]
    unban = guard.split("async def durable_unban_by_username", 1)[1].split(
        "async def durable_member_release", 1
    )[0]
    panel = guard.split("async def durable_member_release", 1)[1]

    assert reason.index("await _create_guard_intent(") < reason.rindex(
        "await reason_admin.moderation_reason_selected"
    )
    assert unban.index("await _create_guard_intent(") < unban.rindex(
        "await group_commands._do_unban"
    )
    assert panel.index("await _create_guard_intent(") < panel.rindex(
        "await member_center.member_action"
    )
    assert "await session.commit()" in _source("app/services/moderation_operations.py").split(
        "async def create_moderation_intent", 1
    )[1].split("async def drop_moderation_intent", 1)[0]


def test_live_business_logic_rechecks_group_after_intent_commit() -> None:
    moderation = _source("app/services/moderation.py")
    execute = moderation.split("async def execute", 1)[1]
    assert ".with_for_update()" in execute
    assert "await can_moderate(" in execute
    assert "await can_moderate_target(" in execute

    member_center = _source("app/handlers/member_center.py")
    member_action = member_center.split("async def member_action", 1)[1].split(
        "async def member_history", 1
    )[0]
    assert "for_update=True" in member_action


def test_guard_covers_auto_mute_and_records_expected_telegram_expiry() -> None:
    guard = _source("app/handlers/moderation_durable_guard.py")
    helper = guard.split("async def _create_guard_intent", 1)[1].split(
        "async def _pending_message", 1
    )[0]
    assert 'action == "warn"' in helper
    assert "current + 1 >= limit and not admin_rank" in helper
    assert 'payload["ends_at"]' in helper
    assert 'payload["had_active_mute"]' in helper
    assert '"target_managed_admin": managed_admin' in helper

    recovery = _source("app/services/moderation_operations.py")
    assert "_mute_matches_intent" in recovery
    assert "MUTE_EXPIRY_TOLERANCE_SECONDS" in recovery
    assert 'payload.get("expect_auto_mute")' in recovery


def test_recovery_requires_transition_from_pre_side_effect_snapshot() -> None:
    recovery = _source("app/services/moderation_operations.py")
    proof = recovery.split("def _state_transition_proves_applied", 1)[1].split(
        "async def _restore_orphan_rank", 1
    )[0]
    assert 'pre_banned = bool(payload.get("pre_banned"))' in proof
    assert 'pre_muted = bool(payload.get("pre_muted"))' in proof
    assert "return _ban_transition_proves_applied(member, payload)" in proof
    assert "pre_banned and not banned" in proof
    assert "pre_muted and not muted" in proof
    assert 'if not pre_muted:' in proof
    assert '_payload_time(payload, "pre_until")' in proof
    assert '_payload_time(payload, "ends_at")' in proof

    ban_proof = recovery.split("def _ban_transition_proves_applied", 1)[1].split(
        "def _state_transition_proves_applied", 1
    )[0]
    assert 'if not bool(payload.get("pre_banned")):' in ban_proof
    assert "return True" in ban_proof
    assert 'pre_until = _payload_time(payload, "pre_until")' in ban_proof
    assert 'expected = _payload_time(payload, "ends_at")' in ban_proof
    assert "return current_matches and not pre_matches" in ban_proof
    assert "return pre_until is not None and current_until is None" in ban_proof


def test_recovery_never_replays_release_side_effects() -> None:
    recovery = _source("app/services/moderation_operations.py")
    recover = recovery.split("async def recover_moderation_operation_intents", 1)[1]
    assert "await bot.get_chat_member(" in recover
    assert "unban_chat_member" not in recover
    assert "restrict_chat_member" not in recover
    assert "_state_transition_proves_applied" in recover


def test_recovery_finalizes_observed_state_and_compensates_orphan_admin_demotion() -> None:
    recovery = _source("app/services/moderation_operations.py")
    assert "async def _finalize_applied_intent" in recovery
    assert "Punishment(" in recovery
    assert "await deactivate_punishments(" in recovery
    assert 'assignment.restore_after_mute = True' in recovery
    assert 'action="remove_by_ban"' in recovery
    compensation = recovery.split("async def _restore_orphan_rank", 1)[1].split(
        "async def _finalize_applied_intent", 1
    )[0]
    assert 'payload.get("target_managed_admin")' in compensation
    assert "ChatMemberStatus.ADMINISTRATOR" in compensation
    assert "await restore_telegram_rank(" in compensation
    assert "return restored" in compensation
    recover = recovery.split("async def recover_moderation_operation_intents", 1)[1]
    assert recover.index("select(Group).where(Group.id == group_id).with_for_update()") < recover.index(
        "await bot.get_chat_member("
    )
    assert "await _matching_log_exists(session, intent)" in recover
    assert "if not compensated:" in recover
    assert "continue" in recover.split("if not compensated:", 1)[1]


def test_recovery_is_wired_at_startup_and_under_supervised_leader() -> None:
    main = _source("app/main.py")
    assert "await ensure_moderation_operation_schema()" in main
    assert "await recover_moderation_operation_intents(bot)" in main

    leader = _source("app/services/background_leader.py")
    assert "_recover_moderation_operations_periodically" in leader
    assert 'name="moderation-operation-recovery"' in leader
    worker = leader.split("async def _run_leader_worker", 1)[1].split(
        "async def leader_background_loop", 1
    )[0]
    assert "moderation_recovery = asyncio.create_task(" in worker
    assert "await stop_task(moderation_recovery, timeout=2.0)" in worker
