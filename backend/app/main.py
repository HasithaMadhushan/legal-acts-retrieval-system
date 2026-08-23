import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.routes import (
    acts,
    auth,
    evaluation,
    exports,
    reading_history,
    references,
    relationships,
    saved_items,
    search,
    sections,
    users,
)
from app.core.config import LEGAL_DISCLAIMER, get_settings
from app.core.error_tracking import init_error_tracking
from app.core.logging import configure_logging, get_logger
from app.core.rate_limit import limiter
from app.db.migrate import run_migrations
from app.db.seed import seed_demo_users
from app.db.session import SessionLocal, get_db
from app.services.storage import get_storage

configure_logging()
init_error_tracking()

logger = get_logger(__name__)
access_logger = get_logger("app.request")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().auto_migrate_on_startup:
        run_migrations()
    with SessionLocal() as db:
        seed_demo_users(db)
    logger.info("app_startup_complete", environment=get_settings().environment)
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log every request with a request id, and expose it on the response.

    Binding the request id (and method/path) via structlog's contextvars means
    any log line emitted by route handlers or services while handling this
    request automatically includes them, without threading a logger through
    every function call.
    """
    request_id = str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id, method=request.method, path=request.url.path
    )
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        access_logger.exception("request_failed", duration_ms=duration_ms)
        raise

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    access_logger.info(
        "request_completed", status_code=response.status_code, duration_ms=duration_ms
    )
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health", tags=["health"])
def health(db: Session = Depends(get_db)) -> JSONResponse:
    current_settings = get_settings()
    checks = {
        "database": _check_database(db),
        "upload_directory": _check_upload_directory(),
        "parser_configuration": _check_parser_configuration(),
    }
    healthy = all(check["ok"] for check in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "ok" if healthy else "degraded",
            "app": current_settings.app_name,
            "checks": checks,
        },
    )


def _check_database(db: Session) -> dict[str, object]:
    try:
        db.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as exc:  # pragma: no cover - defensive, DB connectivity failure
        return {"ok": False, "error": str(exc)}


def _check_upload_directory() -> dict[str, object]:
    ok, error = get_storage().check_health()
    return {"ok": ok, "error": error} if not ok else {"ok": True}


def _check_parser_configuration() -> dict[str, object]:
    known_parsers = {"", "pymupdf", "docling", "ocr"}
    requested = get_settings().doc_parser_primary.strip().lower()
    if requested not in known_parsers:
        return {"ok": False, "error": f"Unknown DOC_PARSER_PRIMARY={requested!r}."}
    return {"ok": True, "parser_requested": requested or "pymupdf"}


@app.get("/api/v1/legal-disclaimer", tags=["safety"])
def legal_disclaimer() -> dict[str, str]:
    return {"disclaimer": LEGAL_DISCLAIMER}


api_prefix = "/api/v1"
app.include_router(auth.router, prefix=api_prefix)
app.include_router(users.router, prefix=api_prefix)
app.include_router(acts.router, prefix=api_prefix)
app.include_router(sections.router, prefix=api_prefix)
app.include_router(references.router, prefix=api_prefix)
app.include_router(search.router, prefix=api_prefix)
app.include_router(relationships.router, prefix=api_prefix)
app.include_router(saved_items.router, prefix=api_prefix)
app.include_router(reading_history.router, prefix=api_prefix)
app.include_router(exports.router, prefix=api_prefix)
app.include_router(evaluation.router, prefix=api_prefix)
