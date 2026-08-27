from pathlib import Path

from app.db.fun_models import GroupMarriage
from app.entertainment_contracts import ENTERTAINMENT_ACTIONS, RELATIONSHIP_ACTIONS, RETIRED_PSEUDO_GAMES
from app.game_contracts import PROPOSALS
from app.game_friendly_results import _proposal_markup
from app.handlers.fun_commands import RANDOM_ACTIONS


ROOT = Path(__file__).resolve().parents[1]


def test_entertainment_catalog_contains_requested_actions_and_no_pseudo_games():
    expected = {"обнять", "поцеловать", "ударить", "уебать", "выебать", "дать дошик", "покормить"}
    assert expected <= ENTERTAINMENT_ACTIONS
    assert RETIRED_PSEUDO_GAMES.isdisjoint(ENTERTAINMENT_ACTIONS)
    assert RANDOM_ACTIONS == {}


def test_family_relationship_domain_is_separate_from_games():
    assert {"поссориться", "поругаться", "подраться", "помириться"} <= RELATIONSHIP_ACTIONS
    assert {"пожениться", "выйти замуж", "сделать предложение"} <= set(PROPOSALS)
    assert set(PROPOSALS.values())
    assert all(kind == "marry" for kind, _ in PROPOSALS.values())


def test_marriage_callbacks_fit_telegram_limit():
    markup = _proposal_markup("marry", 123456, 9876543210, 9876543211)
    callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert all(callbacks)
    assert all(len(value.encode("utf-8")) <= 64 for value in callbacks if value)
    assert callbacks[0].endswith(":yes")
    assert callbacks[1].endswith(":no")


def test_legacy_pseudo_game_handlers_are_not_registered():
    fun = (ROOT / "app/handlers/fun_commands.py").read_text(encoding="utf-8")
    friendly = (ROOT / "app/game_friendly_results.py").read_text(encoding="utf-8")
    tasks = (ROOT / "app/tasks_fun.py").read_text(encoding="utf-8")
    assert "@router.message" not in fun
    assert "RANDOM_ACTIONS: dict[str, list[str]] = {}" in fun
    assert "PROPOSAL_ACTIONS" in friendly
    assert "random.choice(tuple(FUN_ACTIONS))" not in tasks


def test_marriage_is_group_scoped_and_persistent():
    assert GroupMarriage.__tablename__ == "group_marriages"
    columns = set(GroupMarriage.__table__.columns.keys())
    assert {"group_id", "user1_telegram_id", "user2_telegram_id", "active", "created_at", "ended_at"} <= columns
    migration = (ROOT / "alembic/versions/0032_group_marriages.py").read_text(encoding="utf-8")
    assert 'down_revision = "0031_rank_mute_restore"' in migration
    assert '"group_marriages"' in migration


def test_games_and_entertainment_have_separate_entrypoints():
    preferences = (ROOT / "app/handlers/fun_preferences.py").read_text(encoding="utf-8")
    help_module = (ROOT / "app/handlers/fun_help.py").read_text(encoding="utf-8")
    assert 'Command("games")' in preferences
    assert 'OPEN_WORDS = {"развлечения", "развлекательные команды"}' in help_module
    assert "Для настоящих игр используйте /games" in help_module
