from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"

NAV_WORDS = ("назад", "отмена", "главное меню", "к группе", "к настройкам", "к рекламе", "к тариф", "к клиент", "к обращ", "к спис", "к карточ", "к аналит", "к модерац", "к причинам", "к рол", "к контент", "к подпис", "к объяв", "к заяв", "к реклам", "к моим", "к групп")
GENERIC_HELPERS = {"back_to_group", "subscription_back"}


def _string_value(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                parts.append("{…}")
        return "".join(parts)
    return None


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


rows: list[tuple[str, int, str, str]] = []
helper_rows: list[tuple[str, int, str, str]] = []
problems: list[str] = []
for path in sorted(APP.rglob("*.py")):
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        continue
    rel = path.relative_to(ROOT).as_posix()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and _call_name(child) in GENERIC_HELPERS:
                    helper_rows.append((rel, child.lineno, node.name, _call_name(child) or ""))
        if not isinstance(node, ast.Call) or _call_name(node) != "InlineKeyboardButton":
            continue
        kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        text = _string_value(kwargs.get("text"))
        callback = _string_value(kwargs.get("callback_data"))
        if not text or not callback:
            continue
        lowered = text.casefold()
        if not any(word in lowered for word in NAV_WORDS):
            continue
        rows.append((rel, node.lineno, text, callback))
        if "назад" in lowered and callback == "panel:home":
            problems.append(f"{rel}:{node.lineno}: button '{text}' jumps to panel:home")
        if "отмен" in lowered and callback == "panel:home":
            problems.append(f"{rel}:{node.lineno}: cancel button jumps to panel:home")

print(f"Navigation buttons audited: {len(rows)}")
for rel, lineno, text, callback in rows:
    print(f"NAV {rel}:{lineno} | {text} -> {callback}")
print(f"Generic back helpers audited: {len(helper_rows)}")
for rel, lineno, function, helper in helper_rows:
    print(f"HELPER {rel}:{lineno} | {function} uses {helper}")

if problems:
    raise SystemExit("Navigation problems:\n" + "\n".join(problems))
