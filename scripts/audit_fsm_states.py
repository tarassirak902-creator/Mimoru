from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDLERS = ROOT / "app" / "handlers"

errors: list[str] = []
defined: dict[str, tuple[str, int]] = {}
consumers: defaultdict[str, list[tuple[str, int, str]]] = defaultdict(list)
entries: defaultdict[str, list[tuple[str, int, str]]] = defaultdict(list)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def state_refs(node: ast.expr) -> set[str]:
    """Resolve one or more State references, including conditional choices."""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return {f"{node.value.id}.{node.attr}"}
    if isinstance(node, ast.IfExp):
        return state_refs(node.body) | state_refs(node.orelse)
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        refs: set[str] = set()
        for item in node.elts:
            refs |= state_refs(item)
        return refs
    return set()


for path in sorted(HANDLERS.glob("*.py")):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel(path))
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            if any((isinstance(base, ast.Name) and base.id == "StatesGroup") or (isinstance(base, ast.Attribute) and base.attr == "StatesGroup") for base in node.bases):
                for item in node.body:
                    if isinstance(item, (ast.Assign, ast.AnnAssign)):
                        targets = item.targets if isinstance(item, ast.Assign) else [item.target]
                        value = item.value
                        if isinstance(value, ast.Call) and ((isinstance(value.func, ast.Name) and value.func.id == "State") or (isinstance(value.func, ast.Attribute) and value.func.attr == "State")):
                            for target in targets:
                                if isinstance(target, ast.Name):
                                    key = f"{node.name}.{target.id}"
                                    defined[key] = (rel(path), item.lineno)

    for node in tree.body:
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                continue
            if dec.func.attr not in {"message", "callback_query"}:
                continue
            for arg in dec.args:
                for ref in state_refs(arg):
                    if ref in defined:
                        consumers[ref].append((rel(path), node.lineno, node.name))
        for child in ast.walk(node):
            if not isinstance(child, ast.Await) or not isinstance(child.value, ast.Call):
                continue
            call = child.value
            if not (isinstance(call.func, ast.Attribute) and call.func.attr == "set_state" and call.args):
                continue
            for ref in state_refs(call.args[0]):
                entries[ref].append((rel(path), child.lineno, node.name))

for key, (path, line) in sorted(defined.items()):
    if not consumers[key]:
        errors.append(f"{path}:{line}: FSM state {key} has no message/callback consumer")
    if not entries[key]:
        errors.append(f"{path}:{line}: FSM state {key} is never entered with set_state()")

for key, locations in sorted(entries.items()):
    if key not in defined:
        for path, line, name in locations:
            errors.append(f"{path}:{line}:{name}: set_state references unknown state {key}")

print(
    f"FSM audit: {len(defined)} states, {sum(len(v) for v in entries.values())} entries, "
    f"{sum(len(v) for v in consumers.values())} state handlers"
)
if errors:
    for item in errors:
        print("ERROR", item)
    raise SystemExit(f"FSM state audit failed with {len(errors)} error(s)")
print("FSM state coverage: OK")
