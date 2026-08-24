from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"

errors: list[str] = []
count = 0
callback_count = 0
url_count = 0
pay_count = 0

ACTION_FIELDS = {
    "url", "callback_data", "web_app", "login_url", "switch_inline_query",
    "switch_inline_query_current_chat", "switch_inline_query_chosen_chat",
    "callback_game", "pay", "copy_text",
}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def call_is_inline_button(node: ast.Call) -> bool:
    func = node.func
    return (isinstance(func, ast.Name) and func.id == "InlineKeyboardButton") or (
        isinstance(func, ast.Attribute) and func.attr == "InlineKeyboardButton"
    )


def literal_str(node: ast.expr | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


for path in sorted(APP.rglob("*.py")):
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=rel(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not call_is_inline_button(node):
            continue
        count += 1
        kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        text_node = kwargs.get("text")
        if text_node is None and not node.args:
            errors.append(f"{rel(path)}:{node.lineno}: InlineKeyboardButton has no text")

        present_actions: list[str] = []
        for field in ACTION_FIELDS:
            value = kwargs.get(field)
            if value is None:
                continue
            if field == "pay" and isinstance(value, ast.Constant) and value.value is False:
                continue
            if isinstance(value, ast.Constant) and value.value is None:
                continue
            present_actions.append(field)

        if len(present_actions) != 1:
            errors.append(
                f"{rel(path)}:{node.lineno}: InlineKeyboardButton must have exactly one action, got {present_actions or 'none'}"
            )
            continue

        action = present_actions[0]
        if action == "callback_data":
            callback_count += 1
            value = literal_str(kwargs.get("callback_data"))
            if value is not None:
                if not value:
                    errors.append(f"{rel(path)}:{node.lineno}: empty callback_data")
                elif len(value.encode("utf-8")) > 64:
                    errors.append(f"{rel(path)}:{node.lineno}: callback_data exceeds Telegram 64-byte limit")
        elif action == "url":
            url_count += 1
            value = literal_str(kwargs.get("url"))
            if value is not None and not value.startswith(("https://", "http://", "tg://")):
                errors.append(f"{rel(path)}:{node.lineno}: unsupported button URL scheme: {value!r}")
        elif action == "pay":
            pay_count += 1
            value = kwargs.get("pay")
            if not (isinstance(value, ast.Constant) and value.value is True):
                errors.append(f"{rel(path)}:{node.lineno}: pay button must use pay=True")

print(
    f"All inline buttons audited: {count} total, {callback_count} callbacks, "
    f"{url_count} URLs, {pay_count} payment buttons"
)
if errors:
    for item in errors:
        print("ERROR", item)
    raise SystemExit(f"Inline button audit failed with {len(errors)} error(s)")
print("All inline button contracts: OK")
