from __future__ import annotations


# Persistent family/relationship proposals. These are entertainment features,
# not games and must not feed future game statistics.
PROPOSALS = {
    "пожениться": ("marry", "💍 {user1} сделал предложение {user2}. Что ответит {user2}?"),
    "выйти замуж": ("marry", "💍 {user1} сделал предложение {user2}. Что ответит {user2}?"),
    "сделать предложение": ("marry", "💍 {user1} сделал предложение {user2}. Что ответит {user2}?"),
}
PROPOSAL_ACTIONS = frozenset(PROPOSALS)

HISTORY_COMMANDS = {
    "браки": "marry",
}
HISTORY_WORDS = frozenset(HISTORY_COMMANDS)
HISTORY_TITLES = {
    "marry": "💍 Браки группы",
}
