#!/bin/sh
set -eu

backup_dir="${BACKUP_DIR:-/backups}"
retention_days="${BACKUP_RETENTION_DAYS:-14}"
lock_dir="${backup_dir}/.backup.lock"
tmp_file=""

case "$retention_days" in
  ''|*[!0-9]*) echo "BACKUP_RETENTION_DAYS must be a non-negative integer" >&2; exit 2 ;;
esac

mkdir -p "$backup_dir"
umask 077

if ! mkdir "$lock_dir" 2>/dev/null; then
  echo "backup is already running" >&2
  exit 3
fi

cleanup() {
  [ -z "$tmp_file" ] || rm -f "$tmp_file"
  rmdir "$lock_dir" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

stamp="$(date -u +%Y%m%d_%H%M%S)"
final_file="${backup_dir}/moderator_${stamp}.dump"
tmp_file="${final_file}.partial"

PGPASSWORD="${POSTGRES_PASSWORD:-moderator}" pg_dump \
  -h "${POSTGRES_HOST:-postgres}" \
  -p "${POSTGRES_PORT:-5432}" \
  -U "${POSTGRES_USER:-moderator}" \
  -d "${POSTGRES_DB:-moderator}" \
  --no-owner \
  --no-privileges \
  -Fc \
  -f "$tmp_file"

# A custom-format dump is accepted only if PostgreSQL can read its catalogue.
pg_restore --list "$tmp_file" >/dev/null
mv "$tmp_file" "$final_file"
tmp_file=""
chmod 600 "$final_file"
printf '%s\n' "$final_file"

# Retention is applied only after a new verified backup was committed.
find "$backup_dir" -type f -name 'moderator_*.dump' -mtime "+$retention_days" -delete
