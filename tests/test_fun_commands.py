from pathlib import Path

from app.db.fun_models import GroupMarriage
from app.handlers.fun_commands import ACTIONS, FUN_ACTIONS, RANDOM_ACTIONS
from app.handlers.fun_social import PROPOSALS, _proposal_markup


ROOT = Path(__file__).resolve().parents[1]


def test_absurd_fun_command_catalog_is_large_and_contains_requested_actions():
    expected = {
        "обнять",
        "понюхать",
        "понюхать волосы",
        "пнуть под зад",
        "дать подзатыльник",
        "завернуть в плед",
        "украсть носок",
        "отправить на завод",
        "превратить в дошик",
        "наколдовать понос",
        "дать вайфай",
        "сделать админом",
        "снять админку",
        "поженить",
        "засосать",
        "соблазнить",
        "зафрендзонить",
    }
    assert expected <= set(ACTIONS)
    assert len(FUN_ACTIONS) >= 90


def test_random_games_have_multiple_outcomes():
    for action in ("ограбить", "похитить", "подкатить", "ударить", "суд"):
        assert action in RANDOM_ACTIONS
        assert len(RANDOM_ACTIONS[action]) >= 3


def test_social_actions_require_target_acceptance_and_callbacks_fit_telegram_limit():
    assert {"пожениться", "позвать на свидание", "признаться в любви", "предложить любовь", "дуэль", "драка"} <= set(PROPOSALS)
    markup = _proposal_markup("marry", 123456, 9876543210, 9876543211)
    callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert all(callbacks)
    assert all(len(value.encode("utf-8")) <= 64 for value in callbacks if value)
    assert callbacks[0].endswith(":yes")
    assert callbacks[1].endswith(":no")


def test_fun_handlers_do_not_swallow_unknown_reply_messages():
    fun = (ROOT / "app/handlers/fun_commands.py").read_text(encoding="utf-8")
    social = (ROOT / "app/handlers/fun_social.py").read_text(encoding="utf-8")
    assert "F.text.casefold().in_(FUN_ACTIONS)" in fun
    assert "F.text.casefold().in_(PROPOSAL_ACTIONS)" in social
    assert "@router.message(F.chat.type.in_(GROUP_TYPES), F.reply_to_message, F.text)" not in fun
    assert "@router.message(F.chat.type.in_(GROUP_TYPES), F.reply_to_message, F.text)" not in social


def test_marriage_is_group_scoped_and_persistent():
    assert GroupMarriage.__tablename__ == "group_marriages"
    columns = set(GroupMarriage.__table__.columns.keys())
    assert {"group_id", "user1_telegram_id", "user2_telegram_id", "active", "created_at", "ended_at"} <= columns
    migration = (ROOT / "alembic/versions/0032_group_marriages.py").read_text(encoding="utf-8")
    assert 'down_revision = "0031_rank_mute_restore"' in migration
    assert '"group_marriages"' in migration


def test_social_router_precedes_plain_fun_router():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    block = main.split("dp.include_routers(", 1)[1]
    assert block.index("fun_social.router") < block.index("fun_commands.router")
