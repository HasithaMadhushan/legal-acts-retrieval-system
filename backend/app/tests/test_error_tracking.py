from unittest.mock import patch

from app.core.config import get_settings
from app.core.error_tracking import init_error_tracking


def test_init_error_tracking_is_noop_without_dsn(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "sentry_dsn", None)

    with patch("sentry_sdk.init") as mock_init:
        init_error_tracking()

    mock_init.assert_not_called()


def test_init_error_tracking_initializes_sentry_when_dsn_is_set(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "sentry_dsn", "https://example@sentry.example/1")
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "sentry_traces_sample_rate", 0.1)

    with patch("sentry_sdk.init") as mock_init:
        init_error_tracking()

    mock_init.assert_called_once()
    _, kwargs = mock_init.call_args
    assert kwargs["dsn"] == "https://example@sentry.example/1"
    assert kwargs["environment"] == "production"
    assert kwargs["traces_sample_rate"] == 0.1
    # Never send personally identifiable request data (headers, cookies, users) by
    # default; this is a legal-domain app and PII handling must stay opt-in.
    assert kwargs["send_default_pii"] is False
