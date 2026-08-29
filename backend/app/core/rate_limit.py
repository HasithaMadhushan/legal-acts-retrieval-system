"""Request rate limiting.

Uses an in-memory counter per client IP (via `slowapi`/`limits`). Each Gunicorn
worker process keeps its own counters, so with `WEB_CONCURRENCY` workers the
effective ceiling is roughly `AUTH_RATE_LIMIT * WEB_CONCURRENCY` rather than a
single hard limit -- still a meaningful throttle against brute-force/credential
-stuffing and scripted registration, but not an exact one. If this needs to be
precise (or the app scales to multiple hosts), swap in a shared backend (e.g.
Redis) via `Limiter(storage_uri=...)`. See `PRODUCTION_ROADMAP.md`.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

limiter = Limiter(key_func=get_remote_address, enabled=get_settings().rate_limit_enabled)


def auth_rate_limit() -> str:
    """Read the configured auth rate limit lazily so tests can override it."""
    return get_settings().auth_rate_limit


def search_rate_limit() -> str:
    """Bound retrieval work per client; shared storage is required for a global limit."""
    return get_settings().search_rate_limit
