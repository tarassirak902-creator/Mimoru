from pathlib import Path
import ast

files = sorted(Path("alembic/versions").glob("*.py"))
revisions = {}
for path in files:
    tree = ast.parse(path.read_text())
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in {"revision", "down_revision"}:
                values[node.targets[0].id] = ast.literal_eval(node.value)
    revisions[values["revision"]] = (values.get("down_revision"), path.name)
heads = set(revisions)
for parent, _ in revisions.values():
    if parent:
        if parent not in revisions:
            raise SystemExit(f"Missing migration parent: {parent}")
        heads.discard(parent)
if len(heads) != 1:
    raise SystemExit(f"Expected one migration head, got: {sorted(heads)}")
print("Migration chain OK, head:", next(iter(heads)))
