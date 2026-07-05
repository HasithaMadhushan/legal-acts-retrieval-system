"""Optional Sentry error tracking.

Disabled by default (no-op) unless `SENTRY_DSN` is set, which is the correct
default for local development and tests: no external network calls, no signup
required to run the app.
"""

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def init_error_tracking() -> None:
    settings = get_settings()
    if not settings.sentry_dsn:
        return

    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
    )
    logger.info("sentry_initialized", environment=settings.environment)
