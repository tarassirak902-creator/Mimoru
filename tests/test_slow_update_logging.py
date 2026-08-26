from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_slow_update_logging_is_global_and_thresholded() -> None:
    main_source = (ROOT / "app/main.py").read_text(encoding="utf-8")
    middleware_source = (ROOT / "app/middlewares_performance.py").read_text(encoding="utf-8")

    assert "SlowUpdateLoggingMiddleware" in main_source
    assert "dp.update.outer_middleware(slow_update_middleware)" in main_source
    assert "SLOW_UPDATE_THRESHOLD_MS = 750" in middleware_source
    assert '"slow_update"' in middleware_source
    assert "time.perf_counter()" in middleware_source


def test_slow_update_logging_does_not_log_message_or_callback_payload() -> None:
    source = (ROOT / "app/middlewares_performance.py").read_text(encoding="utf-8")

    assert 'context["message_kind"]' in source
    assert 'context["callback_prefix"]' in source
    assert 'context["text"]' not in source
    assert 'context["callback_data"]' not in source
