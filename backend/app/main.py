from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.routes import (
    acts,
    auth,
    evaluation,
    exports,
    references,
    relationships,
    saved_items,
    search,
    sections,
    users,
)
from app.core.config import LEGAL_DISCLAIMER, get_settings
from app.db.migrate import run_migrations
from app.db.seed import seed_demo_users
from app.db.session import SessionLocal, get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().auto_migrate_on_startup:
        run_migrations()
    with SessionLocal() as db:
        seed_demo_users(db)
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
def health(db: Session = Depends(get_db)) -> JSONResponse:
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
            "app": settings.app_name,
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
    try:
        upload_path = settings.upload_path
        upload_path.mkdir(parents=True, exist_ok=True)
        probe_path = upload_path / ".health_check"
        probe_path.write_text("ok", encoding="utf-8")
        probe_path.unlink(missing_ok=True)
        return {"ok": True}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}


def _check_parser_configuration() -> dict[str, object]:
    known_parsers = {"", "pymupdf", "docling", "ocr"}
    requested = settings.doc_parser_primary.strip().lower()
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
app.include_router(exports.router, prefix=api_prefix)
app.include_router(evaluation.router, prefix=api_prefix)
