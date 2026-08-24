from pathlib import Path

from scripts.check_router_registration import (
    discover_router_modules,
    dispatcher_router_order,
    validate_router_registration,
)

ROOT = Path(__file__).resolve().parents[1]


def test_every_handler_router_is_registered_exactly_once() -> None:
    modules = discover_router_modules(ROOT)
    order = dispatcher_router_order(ROOT)
    assert set(order) == set(modules)
    assert len(order) == len(set(order))


def test_catch_all_router_is_last() -> None:
    modules = discover_router_modules(ROOT)
    order = dispatcher_router_order(ROOT)
    catchalls = [
        name
        for name in order
        if modules[name].has_catchall_message or modules[name].has_catchall_edited_message
    ]
    assert catchalls == ["protection"]
    assert order[-1] == "protection"


def test_router_registration_validation_passes() -> None:
    assert validate_router_registration(ROOT) == []
