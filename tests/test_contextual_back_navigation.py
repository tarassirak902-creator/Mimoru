from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_shared_service_cards_keep_entry_context() -> None:
    source = (ROOT / "app/handlers/contextual_back.py").read_text(encoding="utf-8")
    assert '"Платные подписки": "sp"' in source
    assert '"Тестовые периоды": "st"' in source
    assert '"Истекают в течение 7 дней": "se"' in source
    assert 'return f"cl:{source[1:]}"' in source
    assert 'callback_data=f"cp:{source}:{group.id}"' in source
    assert 'callback_data=f"ch:{source}:{group.id}"' in source
    assert 'callback_data=f"cs:{source}:{group.id}"' in source
    assert 'callback_data=f"gc:{source}:{group.id}:{action}"' in source


def test_service_plan_and_confirmation_preserve_context() -> None:
    source = (ROOT / "app/handlers/contextual_back.py").read_text(encoding="utf-8")
    assert 'callback_data=f"pc:{source}:{group.id}:trial:7"' in source
    assert 'callback_data=f"pa:{source}:{group.id}:{plan_code}:{raw_days}"' in source
    assert 'callback_data=f"cp:{source}:{group.id}"' in source
    assert 'callback_data=f"cg:{source}:{group.id}"' in source


def test_member_card_returns_to_originating_list() -> None:
    source = (ROOT / "app/handlers/contextual_back.py").read_text(encoding="utf-8")
    assert '"Недавно активные": (f"people_active:{group_id}"' in source
    assert '"Неактивные 30+ дней": (f"people_inactive:{group_id}"' in source
    assert '"Новички · 7 дней": (f"people_new:{group_id}"' in source
    assert '"Активные предупреждения": (f"active_punishments:{group_id}:warn"' in source
    assert 'return f"complaint:{group_id}:{match.group(1)}", "◀️ К жалобе"' in source


def test_contextual_router_precedes_shared_legacy_handlers() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert main.index("\n        contextual_back.router,") < main.index("\n        group_directory.router,")
    assert main.index("\n        contextual_back.router,") < main.index("\n        member_center.router,")
    assert main.index("\n        contextual_back.router,") < main.index("\n        service_management.router,")
