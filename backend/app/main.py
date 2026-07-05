from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from app.db.seed import seed_demo_users
from app.db.session import SessionLocal, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
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
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


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
