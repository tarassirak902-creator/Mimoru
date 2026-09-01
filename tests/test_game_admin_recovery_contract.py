from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_game_admin_is_explicit_command_and_manager_only() -> None:
    source = read("app/games/admin_handlers.py")
    assert 'Command("game_admin")' in source
    assert 'F.chat.type.in_(GROUP_TYPES)' in source
    assert 'can_manage_group(' in source
    assert 'Управление играми доступно только управляющим группы' in source
    assert '@router.message(F.text)' not in source


def test_game_admin_callbacks_are_bound_to_opener_and_group() -> None:
    source = read("app/games/admin_handlers.py")
    assert 'callback.from_user.id != requester_id' in source
    assert 'callback.message.chat.id != group.telegram_chat_id' in source
    assert 'Эта служебная карточка открыта другим управляющим' in source
    assert 'gm:adm:close:' in source


def test_force_cancel_requires_confirmation_and_does_not_apply_results() -> None:
    source = read("app/games/admin_handlers.py")
    assert 'gm:adm:cancel:' in source
    assert 'gm:adm:confirm:' in source
    assert 'manager.cancel_game(session, game_id=game.id, reason="admin_cancelled")' in source
    assert 'apply_game_result' not in source
    assert 'retire_active_messages(' in source
    assert 'Игра принудительно отменена управляющим группы.' in source


def test_panel_recovery_reuses_shared_panel_service() -> None:
    source = read("app/games/admin_handlers.py")
    assert 'gm:adm:panel:' in source
    assert 'ensure_game_panel(bot, session, group=group, pin=True)' in source


def test_game_admin_router_precedes_generic_game_router() -> None:
    wiring = read("app/handlers/fun_preferences.py")
    assert 'game_admin_handlers.router' in wiring
    assert wiring.index('game_admin_handlers.router') < wiring.index('game_handlers.router')
