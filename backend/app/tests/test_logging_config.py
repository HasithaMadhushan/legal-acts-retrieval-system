import logging

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger


def test_configure_logging_uses_json_renderer_when_configured(monkeypatch, capsys):
    settings = get_settings()
    monkeypatch.setattr(settings, "log_format", "json")
    monkeypatch.setattr(settings, "log_level", "INFO")

    configure_logging()
    get_logger("test.logger").info("hello_world", foo="bar")

    captured = capsys.readouterr()
    assert '"event": "hello_world"' in captured.out
    assert '"foo": "bar"' in captured.out


def test_configure_logging_uses_console_renderer_by_default(monkeypatch, capsys):
    settings = get_settings()
    monkeypatch.setattr(settings, "log_format", "console")
    monkeypatch.setattr(settings, "log_level", "INFO")

    configure_logging()
    get_logger("test.logger").info("hello_world", foo="bar")

    captured = capsys.readouterr()
    assert "hello_world" in captured.out
    assert "foo" in captured.out
    # Console output is not valid single-line JSON.
    assert '"event":' not in captured.out


def test_configure_logging_respects_log_level(monkeypatch, capsys):
    settings = get_settings()
    monkeypatch.setattr(settings, "log_format", "json")
    monkeypatch.setattr(settings, "log_level", "WARNING")

    configure_logging()
    get_logger("test.logger").info("should_be_suppressed")
    get_logger("test.logger").warning("should_appear")

    captured = capsys.readouterr()
    assert "should_be_suppressed" not in captured.out
    assert "should_appear" in captured.out


def test_get_logger_returns_a_working_structlog_logger(monkeypatch, capsys):
    settings = get_settings()
    monkeypatch.setattr(settings, "log_format", "json")
    monkeypatch.setattr(settings, "log_level", "INFO")
    configure_logging()

    # structlog.get_logger() returns a lazy proxy that only resolves into the
    # configured BoundLogger on first use, so assert on behavior, not type.
    logger = get_logger("app.something")
    logger.info("logger_is_working")

    captured = capsys.readouterr()
    assert "logger_is_working" in captured.out


def teardown_module() -> None:
    # Restore a sane global logging config for any tests that run afterwards.
    settings = get_settings()
    settings.log_format = "console"
    settings.log_level = "INFO"
    configure_logging()
    logging.getLogger().handlers = []
