from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.legal_safety import ensure_no_legal_advice_query
from app.core.rate_limit import limiter, search_rate_limit
from app.core.roles import ProcessingStatus, RelationshipType, VerificationStatus
from app.db.session import get_db
from app.models.legal_act import LegalAct
from app.models.user import User
from app.schemas.search import (
    SEMANTIC_SEARCH_DISABLED,
    SEMANTIC_SEARCH_NOT_READY,
    SearchRequestedMode,
    SearchResponse,
    SuggestResponse,
)
from app.services.search_service import search
from app.services.semantic_readiness import probe_semantic_readiness
from app.services.text_cleaner import like_contains

router = APIRouter(prefix="/search", tags=["search"])


@dataclass(frozen=True)
class SearchParameters:
    q: str = Query(default="", max_length=200)
    year: int | None = None
    act_number: str | None = None
    category: str | None = None
    processing_status: ProcessingStatus | None = None
    relationship_type: RelationshipType | None = None
    verification_status: VerificationStatus | None = None
    mapped_status: Literal["mapped", "unresolved"] | None = None
    search_mode: SearchRequestedMode = "all"
    limit: int = Query(default=25, ge=1, le=100)
    offset: int = Query(default=0, ge=0)


@router.get(
    "",
    responses={
        400: {"description": SEMANTIC_SEARCH_DISABLED},
        503: {"description": SEMANTIC_SEARCH_NOT_READY},
    },
)
@limiter.limit(search_rate_limit)
def search_endpoint(
    request: Request,
    params: SearchParameters = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SearchResponse:
    query = params.q.strip()
    ensure_no_legal_advice_query(query)
    if params.search_mode == "semantic":
        _reject_unservable_semantic_search(db)
    return search(
        db,
        query=query,
        role=current_user.role,
        year=params.year,
        act_number=params.act_number,
        category=params.category,
        processing_status=params.processing_status,
        relationship_type=params.relationship_type,
        verification_status=params.verification_status,
        mapped_status=params.mapped_status,
        search_mode=params.search_mode,
        limit=params.limit,
        offset=params.offset,
    )


def _reject_unservable_semantic_search(db: Session) -> None:
    if not get_settings().semantic_search_enabled:
        raise HTTPException(status_code=400, detail=SEMANTIC_SEARCH_DISABLED)
    readiness = probe_semantic_readiness(db)
    if not readiness.ready:
        raise HTTPException(status_code=503, detail=SEMANTIC_SEARCH_NOT_READY)


@router.get("/suggest", response_model=SuggestResponse)
def suggest(
    q: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SuggestResponse:
    suggestions = [
        act.title
        for act in db.query(LegalAct)
        .filter(LegalAct.normalized_title.ilike(like_contains(q.lower()), escape="\\"))
        .limit(8)
        .all()
    ]
    return SuggestResponse(suggestions=suggestions)
