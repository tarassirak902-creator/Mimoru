from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
HANDLERS = APP / "handlers"


def decorator_is_handler(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "router"
        and func.attr in {
            "message", "edited_message", "callback_query", "pre_checkout_query",
            "chat_join_request", "chat_member", "my_chat_member",
        }
    )


def main() -> int:
    python_files = sorted(APP.rglob("*.py"))
    handlers = 0
    pass_only: list[str] = []
    markers: list[str] = []

    for path in python_files:
        source = path.read_text(encoding="utf-8")
        for marker in ("TODO", "FIXME", "NotImplementedError"):
            if marker in source:
                markers.append(f"{path.relative_to(ROOT)}: contains {marker}")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if any(decorator_is_handler(dec) for dec in node.decorator_list):
                    handlers += 1
                body = [item for item in node.body if not isinstance(item, ast.Expr) or not isinstance(item.value, ast.Constant) or not isinstance(item.value.value, str)]
                if body and all(isinstance(item, ast.Pass) for item in body):
                    pass_only.append(f"{path.relative_to(ROOT)}:{node.lineno} {node.name}")

    router_modules = [p for p in HANDLERS.glob("*.py") if p.name != "__init__.py"]
    missing_router = []
    for path in router_modules:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        has_router = any(
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "router" for target in node.targets)
            for node in tree.body
        )
        if not has_router:
            missing_router.append(str(path.relative_to(ROOT)))

    if pass_only or markers or missing_router:
        print("Functionality surface check failed")
        for item in pass_only + markers + missing_router:
            print("-", item)
        return 1

    print(f"Functionality surface: OK ({len(python_files)} app files, {handlers} decorated handlers, {len(router_modules)} router modules)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
