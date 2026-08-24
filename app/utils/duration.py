import re

UNITS = {
    "с": 1, "сек": 1,
    "м": 60, "мин": 60,
    "ч": 3600, "час": 3600,
    "д": 86400, "дн": 86400,
    "н": 604800, "нед": 604800,
}
DURATION_RE = re.compile(r"^(\d+)(с|сек|м|мин|ч|час|д|дн|н|нед)$", re.IGNORECASE)


def parse_duration(token: str | None) -> int | None:
    if not token:
        return None
    match = DURATION_RE.fullmatch(token.strip().lower())
    if not match:
        return None
    return int(match.group(1)) * UNITS[match.group(2)]


def human_duration(seconds: int) -> str:
    for unit_seconds, label in ((604800, "нед."), (86400, "дн."), (3600, "ч."), (60, "мин.")):
        if seconds % unit_seconds == 0:
            return f"{seconds // unit_seconds} {label}"
    return f"{seconds} сек."
