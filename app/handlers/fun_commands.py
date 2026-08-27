from __future__ import annotations

import random

from aiogram import Router

from app.entertainment_contracts import ENTERTAINMENT_ACTIONS, RELATIONSHIP_ACTIONS


# Compatibility module for callers that still import the old catalogue helpers.
# The router is intentionally empty: production reply handling lives in
# game_friendly_results and this module no longer defines any games.
router = Router(name=__name__)
ACTION_COOLDOWN_SECONDS = 3.0
_action_cooldowns: dict[tuple[int, int], float] = {}

ACTIONS = {action: "{user1} → {user2}: «" + action + "»." for action in ENTERTAINMENT_ACTIONS | RELATIONSHIP_ACTIONS}
ACTIONS.update({
    "обнять": "{user1} обнял {user2}. Кажется, кому-то сегодня не хватает внимания 🫂",
    "поцеловать": "{user1} поцеловал {user2}. Так-так-так… 😏",
    "ударить": "{user1} ударил {user2}. Шуточный раунд окончен.",
    "уебать": "{user1} уебал {user2}. Только в рамках чатовой шутки 👊",
    "выебать": "{user1} выбрал для {user2} максимально взрослую шутку 😏",
    "дать дошик": "{user1} поделился дошиком с {user2}. Вот она — настоящая любовь.",
    "накормить": "{user1} накормил {user2}. Приятного аппетита.",
    "покормить": "{user1} покормил {user2}. Приятного аппетита.",
    "поссориться": "{user1} поссорился с {user2}. Причина уже забыта.",
    "поругаться": "{user1} поругался с {user2}. Чат ждёт примирения.",
    "подраться": "{user1} и {user2} устроили шуточную драку. Победителей здесь нет.",
    "помириться": "{user1} помирился с {user2}. Мир восстановлен 🤝",
})

# Kept as an empty compatibility symbol so imports fail closed rather than
# silently reviving old pseudo-game behaviour.
RANDOM_ACTIONS: dict[str, list[str]] = {}
RARE_EVENTS: dict[str, list[tuple[int, str]]] = {}
FUN_ACTIONS = frozenset(ACTIONS)


def _name(user) -> str:
    if getattr(user, "username", None):
        return f"@{user.username}"
    return getattr(user, "full_name", None) or str(user.id)


def _pick_text(action: str) -> str:
    if action not in ACTIONS:
        raise KeyError(action)
    return ACTIONS[action]
