from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_checks() -> list[str]:
    errors: list[str] = []
    backup = (ROOT / "scripts_backup.sh").read_text(encoding="utf-8")
    required_backup_fragments = {
        "temporary backup file": ".partial",
        "backup validation": "pg_restore --list",
        "atomic publication": 'mv "$tmp_file" "$final_file"',
        "restrictive permissions": 'chmod 600 "$final_file"',
        "concurrency lock": ".backup.lock",
        "cleanup trap": "trap cleanup",
        "UTC timestamp": "date -u",
    }
    for label, fragment in required_backup_fragments.items():
        if fragment not in backup:
            errors.append(f"backup script misses {label}: {fragment}")
    if backup.find("pg_restore --list") > backup.find('mv "$tmp_file" "$final_file"'):
        errors.append("backup is published before validation")
    if backup.find('find "$backup_dir"') < backup.find('mv "$tmp_file" "$final_file"'):
        errors.append("retention runs before a verified backup is published")

    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    if "scripts_backup.sh:/scripts_backup.sh:ro" not in compose:
        errors.append("backup script is not mounted read-only")
    if "backups:/backups" not in compose:
        errors.append("backup volume is not persistent")

    logging_tree = ast.parse((ROOT / "app/core/logging.py").read_text(encoding="utf-8"))
    imported_redactor = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "app.core.log_safety"
        and any(alias.name == "redact_event_dict" for alias in node.names)
        for node in logging_tree.body
    )
    if not imported_redactor:
        errors.append("structured logging does not import the redaction processor")
    logging_text = (ROOT / "app/core/logging.py").read_text(encoding="utf-8")
    for fragment in ("redact_event_dict", "format_exc_info", "JSONRenderer"):
        if fragment not in logging_text:
            errors.append(f"structured logging misses processor: {fragment}")
    if logging_text.find("redact_event_dict") > logging_text.find("JSONRenderer"):
        errors.append("redaction must happen before JSON rendering")

    return errors


def main() -> int:
    errors = run_checks()
    if errors:
        print("Operational resilience check failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Operational resilience check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
