from app.games import game_registry
from app.games.mafia.game import MafiaGame, MafiaPhase, mafia_definition


def test_mafia_is_registered() -> None:
    definition = game_registry.require("mafia")
    assert definition == mafia_definition
    assert definition.min_players == 4
    assert definition.max_players == 15
    assert definition.exclusive_group_game is True
    assert definition.uses_private_mapping is True
    assert isinstance(game_registry.engine("mafia"), MafiaGame)


def test_mafia_state_machine_has_required_phases() -> None:
    assert {phase.value for phase in MafiaPhase} == {
        "role_assignment",
        "day_start",
        "discussion",
        "day_voting",
        "voting_result",
        "night_start",
        "night_actions",
        "night_result",
        "finished",
    }


def test_mafia_role_deck_contains_core_roles() -> None:
    roles = MafiaGame._role_deck(8)
    assert len(roles) == 8
    assert roles.count("mafia") == 2
    assert roles.count("doctor") == 1
    assert roles.count("commissioner") == 1
    assert roles.count("civilian") == 4
