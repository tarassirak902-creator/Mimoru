from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_member_card_rewrites_nested_routes_with_origin() -> None:
    source = (ROOT / "app/handlers/member_navigation.py").read_text(encoding="utf-8")
    assert 'data = f"mh:{source}:{group_id}:{user_id}"' in source
    assert 'data = f"mt:{source}:{group_id}:{user_id}"' in source
    assert 'data = f"mn:{source}:{group_id}:{user_id}"' in source
    assert 'callback_data=f"mc:{source}:{group.id}:{user_id}"' in source


def test_member_tags_and_notes_keep_origin_through_text_forms() -> None:
    source = (ROOT / "app/handlers/member_navigation.py").read_text(encoding="utf-8")
    assert '_cancel_callback=f"mt:{source}:{group_id}:{user_id}"' in source
    assert '_cancel_callback=f"mn:{source}:{group_id}:{user_id}"' in source
    assert 'member_source=source' in source
    assert 'source = str(data.get("member_source") or "u")' in source


def test_member_origin_maps_cover_shared_lists_and_complaints() -> None:
    source = (ROOT / "app/handlers/member_navigation.py").read_text(encoding="utf-8")
    for label in (
        "Недавно активные",
        "Неактивные 30+ дней",
        "Новички · 7 дней",
        "Требуют внимания",
        "Активные предупреждения",
        "Активные муты",
        "Активные блокировки",
    ):
        assert label in source
    assert 'return f"complaint:{group_id}:{source[1:]}", "◀️ К жалобе"' in source


def test_member_navigation_router_wins_before_legacy_routes() -> None:
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert main.index("\n        member_navigation.router,") < main.index("\n        contextual_back.router,")
    assert main.index("\n        member_navigation.router,") < main.index("\n        member_center.router,")
