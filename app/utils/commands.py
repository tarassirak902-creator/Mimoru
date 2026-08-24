from dataclasses import dataclass

from app.utils.duration import parse_duration

ALIASES = {
    "снять предупреждение": "unwarn", "снять пред": "unwarn", "минус пред": "unwarn",
    "снять мут": "unmute", "снять бан": "unban",
    "бан": "ban", "забанить": "ban", "блок": "ban",
    "разбан": "unban", "разбанить": "unban",
    "мут": "mute", "замутить": "mute", "тишина": "mute",
    "размут": "unmute", "размутить": "unmute",
    "пред": "warn", "варн": "warn", "предупреждение": "warn",
    "преды": "warnings", "варны": "warnings",
    "инфо": "info", "карточка": "info", "кто ты": "info", "кто это": "info",
    "история": "history", "нарушения": "history",
}


@dataclass(slots=True)
class ParsedCommand:
    action: str
    duration: int | None
    reason: str


def normalize(text: str) -> str:
    return " ".join(text.lower().replace("ё", "е").strip(" .,!\n\t").split())


def parse_command(text: str) -> ParsedCommand | None:
    normalized = normalize(text)
    alias = next((a for a in sorted(ALIASES, key=len, reverse=True) if normalized == a or normalized.startswith(a + " ")), None)
    if alias is None:
        return None
    action = ALIASES[alias]
    rest = normalized[len(alias):].strip()
    parts = rest.split()
    duration = parse_duration(parts[0]) if parts else None
    reason_start = 1 if duration is not None else 0
    reason = " ".join(parts[reason_start:]) or "Не указана"
    return ParsedCommand(action=action, duration=duration, reason=reason)
