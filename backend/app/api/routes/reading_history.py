from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.core.roles import ReadingHistoryItemType
from app.db.session import get_db
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.models.reading_history import ReadingHistoryItem
from app.models.user import User
from app.schemas.reading_history import (
    ReadingHistoryCreate,
    ReadingHistoryListResponse,
    ReadingHistoryRead,
)

router = APIRouter(prefix="/reading-history", tags=["reading-history"])


def _history_href(item_type: ReadingHistoryItemType, act_id: str, section_id: str | None) -> str:
    if item_type == ReadingHistoryItemType.SECTION and section_id:
        return f"/sections/{section_id}"
    return f"/acts/{act_id}"


def _enrich_item(item: ReadingHistoryItem) -> ReadingHistoryRead:
    act = item.act
    section = item.section
    return ReadingHistoryRead(
        id=item.id,
        item_type=item.item_type,
        act_id=item.act_id,
        section_id=item.section_id,
        viewed_at=item.viewed_at,
        act_title=act.title if act else "Unknown Act",
        act_number=act.act_number if act else None,
        act_year=act.year if act else None,
        section_number=section.section_number if section else None,
        section_heading=section.heading if section else None,
        href=_history_href(item.item_type, item.act_id, item.section_id),
    )


@router.get("", response_model=ReadingHistoryListResponse)
def list_reading_history(
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReadingHistoryListResponse:
    query = (
        db.query(ReadingHistoryItem)
        .options(joinedload(ReadingHistoryItem.act), joinedload(ReadingHistoryItem.section))
        .filter(ReadingHistoryItem.user_id == current_user.id)
    )
    total_results = query.count()
    items = query.order_by(ReadingHistoryItem.viewed_at.desc()).limit(limit).all()
    return ReadingHistoryListResponse(
        items=[_enrich_item(item) for item in items],
        total_results=total_results,
    )


@router.post("", response_model=ReadingHistoryRead, status_code=201)
def record_reading_history(
    payload: ReadingHistoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReadingHistoryRead:
    act = db.get(LegalAct, payload.act_id)
    if not act:
        raise HTTPException(status_code=404, detail="Act not found.")

    section = None
    if payload.item_type == ReadingHistoryItemType.SECTION:
        if not payload.section_id:
            raise HTTPException(
                status_code=400, detail="section_id is required for SECTION history."
            )
        section = db.get(ActSection, payload.section_id)
        if not section or section.act_id != payload.act_id:
            raise HTTPException(status_code=404, detail="Section not found for this Act.")

    query = db.query(ReadingHistoryItem).filter(
        ReadingHistoryItem.user_id == current_user.id,
        ReadingHistoryItem.item_type == payload.item_type,
        ReadingHistoryItem.act_id == payload.act_id,
    )
    if payload.item_type == ReadingHistoryItemType.SECTION:
        query = query.filter(ReadingHistoryItem.section_id == payload.section_id)
    else:
        query = query.filter(ReadingHistoryItem.section_id.is_(None))

    existing = query.first()
    now = datetime.now(UTC)
    if existing:
        existing.viewed_at = now
        item = existing
    else:
        item = ReadingHistoryItem(
            user_id=current_user.id,
            item_type=payload.item_type,
            act_id=payload.act_id,
            section_id=(
                payload.section_id
                if payload.item_type == ReadingHistoryItemType.SECTION
                else None
            ),
            viewed_at=now,
        )
        db.add(item)
    db.commit()
    db.refresh(item)
    item = (
        db.query(ReadingHistoryItem)
        .options(joinedload(ReadingHistoryItem.act), joinedload(ReadingHistoryItem.section))
        .filter(ReadingHistoryItem.id == item.id)
        .one()
    )
    return _enrich_item(item)
