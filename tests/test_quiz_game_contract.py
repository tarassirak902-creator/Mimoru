from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_quiz_is_registered_and_routed_before_generic_game_handlers() -> None:
    registry = (ROOT / "app/games/__init__.py").read_text(encoding="utf-8")
    routing = (ROOT / "app/handlers/fun_preferences.py").read_text(encoding="utf-8")

    assert "from app.games.quiz import QuizGame, quiz_definition" in registry
    assert "game_registry.register(quiz_definition, QuizGame())" in registry
    quiz = "router.include_router(quiz_handlers.router)"
    generic = "router.include_router(game_handlers.router)"
    assert quiz in routing and generic in routing
    assert routing.index(quiz) < routing.index(generic)


def test_quiz_uses_callback_answers_and_no_plain_message_gameplay() -> None:
    handlers = (ROOT / "app/games/quiz/handlers.py").read_text(encoding="utf-8")

    assert "@router.message" not in handlers
    assert 'r"^gm:qa:\\d+:\\d+:\\d+$"' in handlers
    assert "game.phase_seq != phase_seq" in handlers
    assert "Ваш ответ уже принят" in handlers
    assert "Вы не участвуете в этом Квизе" in handlers


def test_quiz_engine_persists_rounds_and_handles_timeouts() -> None:
    source = (ROOT / "app/games/quiz/game.py").read_text(encoding="utf-8")

    assert 'game.phase = QuizPhase.QUESTION.value' in source
    assert 'game.phase = QuizPhase.ROUND_RESULT.value' in source
    assert '"rounds": rounds' in source
    assert "async def handle_timeout" in source
    assert "async def restore" in source
    assert "expected_phase_seq" in source
    assert 'action_type="quiz_answer"' in source
    assert "player.score += 1" in source
    assert "await apply_game_result(" in source
    assert "GameResult(" in source


def test_quiz_lobby_has_dedicated_start_and_timeout() -> None:
    source = (ROOT / "app/games/lobby.py").read_text(encoding="utf-8")

    assert '"quiz"' in source.split("_TIMED_LOBBY_GAMES", 1)[1].split("}", 1)[0]
    assert 'elif game_type == "quiz":' in source
    assert 'start_callback = f"gm:qs:{game_id}"' in source


def test_quiz_ui_reuses_one_phase_message() -> None:
    source = (ROOT / "app/games/quiz/presentation.py").read_text(encoding="utf-8")

    assert "upsert_phase_message(" in source
    assert 'kind="phase"' in source
    assert "ensure_game_panel(" in source
    assert "bot.send_message" not in source
