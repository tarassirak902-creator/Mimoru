from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RouterModule:
    name: str
    path: Path
    has_catchall_message: bool
    has_catchall_edited_message: bool


def _is_router_assignment(node: ast.Assign) -> bool:
    if not any(isinstance(target, ast.Name) and target.id == "router" for target in node.targets):
        return False
    call = node.value
    return (
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "Router"
    )


def _catchall_events(tree: ast.Module) -> tuple[bool, bool]:
    message = False
    edited = False
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or decorator.args or decorator.keywords:
                continue
            func = decorator.func
            if not isinstance(func, ast.Attribute):
                continue
            if not isinstance(func.value, ast.Name) or func.value.id != "router":
                continue
            if func.attr == "message":
                message = True
            elif func.attr == "edited_message":
                edited = True
    return message, edited


def discover_router_modules(root: Path) -> dict[str, RouterModule]:
    handlers_dir = root / "app" / "handlers"
    modules: dict[str, RouterModule] = {}
    for path in sorted(handlers_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if not any(isinstance(node, ast.Assign) and _is_router_assignment(node) for node in tree.body):
            continue
        catch_message, catch_edited = _catchall_events(tree)
        modules[path.stem] = RouterModule(
            name=path.stem,
            path=path,
            has_catchall_message=catch_message,
            has_catchall_edited_message=catch_edited,
        )
    return modules


def dispatcher_router_order(root: Path) -> list[str]:
    main_path = root / "app" / "main.py"
    tree = ast.parse(main_path.read_text(encoding="utf-8"), filename=str(main_path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "include_routers":
            continue
        order: list[str] = []
        for arg in node.args:
            if (
                isinstance(arg, ast.Attribute)
                and arg.attr == "router"
                and isinstance(arg.value, ast.Name)
            ):
                order.append(arg.value.id)
            else:
                raise AssertionError("include_routers() must receive module.router references only")
        return order
    raise AssertionError("Dispatcher.include_routers() call not found")


def validate_router_registration(root: Path) -> list[str]:
    modules = discover_router_modules(root)
    order = dispatcher_router_order(root)
    errors: list[str] = []

    missing = sorted(set(modules) - set(order))
    unknown = sorted(set(order) - set(modules))
    duplicates = sorted({name for name in order if order.count(name) > 1})
    if missing:
        errors.append("routers not registered: " + ", ".join(missing))
    if unknown:
        errors.append("registered modules without Router(): " + ", ".join(unknown))
    if duplicates:
        errors.append("routers registered more than once: " + ", ".join(duplicates))

    for event_name, field in (
        ("message", "has_catchall_message"),
        ("edited_message", "has_catchall_edited_message"),
    ):
        catchalls = [name for name in order if getattr(modules[name], field)]
        if len(catchalls) > 1:
            errors.append(f"multiple catch-all {event_name} routers: {', '.join(catchalls)}")
        if catchalls:
            catchall = catchalls[0]
            if order[-1] != catchall:
                errors.append(
                    f"catch-all {event_name} router '{catchall}' must be last; "
                    f"current last router is '{order[-1]}'"
                )

    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = validate_router_registration(root)
    if errors:
        for error in errors:
            print("ERROR:", error)
        return 1
    modules = discover_router_modules(root)
    order = dispatcher_router_order(root)
    print(f"Router registration OK: {len(order)} routers")
    catchalls = [
        module.name
        for module in modules.values()
        if module.has_catchall_message or module.has_catchall_edited_message
    ]
    print("Catch-all routers:", ", ".join(catchalls) or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
