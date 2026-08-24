from __future__ import annotations

import re
from urllib.parse import urlparse

URL_RE = re.compile(r"(?:(?:https?://|www\.)[^\s<>()]+|(?:t\.me|telegram\.me)/[^\s<>()]+)", re.I)


def normalize_domain(value: str) -> str:
    raw = value.strip().casefold().rstrip(".,;:!?)\"]}")
    if not raw:
        raise ValueError("Пустой домен")
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    host = (parsed.hostname or "").removeprefix("www.").rstrip(".")
    if not host or "." not in host:
        raise ValueError("Некорректный домен")
    if len(host) > 253 or any(not part or len(part) > 63 for part in host.split(".")):
        raise ValueError("Некорректный домен")
    return host


def extract_domains(text: str) -> set[str]:
    domains: set[str] = set()
    for match in URL_RE.finditer(text):
        candidate = match.group(0)
        try:
            domains.add(normalize_domain(candidate))
        except ValueError:
            continue
    return domains


def contains_blocked_link(text: str, allowed_domains: set[str]) -> bool:
    for domain in extract_domains(text):
        if domain in allowed_domains:
            continue
        if any(domain.endswith("." + allowed) for allowed in allowed_domains):
            continue
        return True
    return False
