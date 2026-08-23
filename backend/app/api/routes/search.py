from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.legal_safety import ensure_no_legal_advice_query
from app.core.roles import ProcessingStatus, RelationshipType, VerificationStatus
from app.db.session import get_db
from app.models.legal_act import LegalAct
from app.models.user import User
from app.schemas.search import SearchResponse, SuggestResponse
from app.services.search_service import search

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
def search_endpoint(
    q: str = Query(default="", max_length=200),
    year: int | None = None,
    act_number: str | None = None,
    category: str | None = None,
    processing_status: ProcessingStatus | None = None,
    relationship_type: RelationshipType | None = None,
    verification_status: VerificationStatus | None = None,
    mapped_status: Literal["mapped", "unresolved"] | None = None,
    search_mode: Literal["all", "keyword", "semantic"] = "all",
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    role_view: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SearchResponse:
    query = q.strip()
    ensure_no_legal_advice_query(query)
    if search_mode == "semantic":
        raise HTTPException(
            status_code=501,
            detail="Semantic search is not available yet. Use Keyword or All methods.",
        )
    return search(
        db,
        query=query,
        role=current_user.role,
        year=year,
        act_number=act_number,
        category=category,
        processing_status=processing_status,
        relationship_type=relationship_type,
        verification_status=verification_status,
        mapped_status=mapped_status,
        limit=limit,
        offset=offset,
    )


@router.get("/suggest", response_model=SuggestResponse)
def suggest(
    q: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SuggestResponse:
    suggestions = [
        act.title
        for act in db.query(LegalAct)
        .filter(LegalAct.normalized_title.ilike(f"%{q.lower()}%"))
        .limit(8)
        .all()
    ]
    return SuggestResponse(suggestions=suggestions)
