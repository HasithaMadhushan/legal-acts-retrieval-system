from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_lawyer_or_admin
from app.core.roles import RelationshipType, SavedItemType, VerificationStatus
from app.db.session import get_db
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.models.legal_reference import LegalReference
from app.models.saved_item import SavedItem
from app.models.user import User
from app.schemas.saved_item import (
    SavedItemCreate,
    SavedItemListResponse,
    SavedItemRead,
    SavedItemUpdate,
)
from app.services.saved_item_service import enrich_saved_item

router = APIRouter(prefix="/saved-items", tags=["saved-items"])


@router.get("", response_model=SavedItemListResponse)
def list_saved_items(
    item_type: SavedItemType | None = None,
    act_id: str | None = None,
    relationship_type: RelationshipType | None = None,
    verification_status: VerificationStatus | None = None,
    mapped_status: str | None = Query(default=None, pattern="^(mapped|unresolved)$"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_lawyer_or_admin),
) -> dict:
    query = _saved_item_query(db).filter(SavedItem.user_id == current_user.id)
    if item_type:
        query = query.filter(SavedItem.item_type == item_type)
    if act_id:
        query = query.filter(
            or_(
                SavedItem.act_id == act_id,
                SavedItem.section.has(ActSection.act_id == act_id),
                SavedItem.reference.has(
                    or_(
                        LegalReference.source_act_id == act_id,
                        LegalReference.target_act_id == act_id,
                    )
                ),
            )
        )
    if relationship_type:
        query = query.filter(
            SavedItem.reference.has(LegalReference.relationship_type == relationship_type)
        )
    if verification_status:
        query = query.filter(
            or_(
                SavedItem.section.has(
                    ActSection.verification_status == verification_status
                ),
                SavedItem.reference.has(
                    LegalReference.verification_status == verification_status
                ),
            )
        )
    if mapped_status:
        query = query.filter(_mapped_status_filter(mapped_status))

    total_results = query.count()
    items = (
        query.order_by(SavedItem.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "items": [enrich_saved_item(item) for item in items],
        "total_results": total_results,
        "limit": limit,
        "offset": offset,
        "counts_by_type": _counts_by_type(db, current_user.id),
    }


@router.post("", response_model=SavedItemRead, status_code=201)
def create_saved_item(
    payload: SavedItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_lawyer_or_admin),
) -> dict:
    values = _validated_target_values(db, payload)
    duplicate = _duplicate_saved_item(db, current_user.id, payload.item_type, values)
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This item is already saved in your workspace.",
        )
    item = SavedItem(
        user_id=current_user.id,
        item_type=payload.item_type,
        note=payload.note,
        **values,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return enrich_saved_item(item)


@router.patch("/{item_id}", response_model=SavedItemRead)
def update_saved_item(
    item_id: str,
    payload: SavedItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_lawyer_or_admin),
) -> dict:
    item = _saved_item_query(db).filter(SavedItem.id == item_id).first()
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Saved item not found.")
    item.note = payload.note
    db.commit()
    db.refresh(item)
    return enrich_saved_item(item)


@router.delete("/{item_id}")
def delete_saved_item(
    item_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_lawyer_or_admin),
) -> dict:
    item = db.get(SavedItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Saved item not found.")
    db.delete(item)
    db.commit()
    return {"detail": "Saved item deleted."}


def _saved_item_query(db: Session):
    return db.query(SavedItem).options(
        joinedload(SavedItem.act),
        joinedload(SavedItem.section).joinedload(ActSection.act),
        joinedload(SavedItem.reference).joinedload(LegalReference.source_act),
        joinedload(SavedItem.reference).joinedload(LegalReference.source_section),
        joinedload(SavedItem.reference).joinedload(LegalReference.target_act),
        joinedload(SavedItem.reference).joinedload(LegalReference.target_section),
    )


def _validated_target_values(db: Session, payload: SavedItemCreate) -> dict[str, str | None]:
    if payload.item_type == SavedItemType.ACT:
        if not payload.act_id:
            raise HTTPException(status_code=400, detail="Act ID is required for saved Acts.")
        act = db.get(LegalAct, payload.act_id)
        if not act:
            raise HTTPException(status_code=404, detail="Act not found.")
        return {"act_id": act.id, "section_id": None, "reference_id": None}

    if payload.item_type == SavedItemType.SECTION:
        if not payload.section_id:
            raise HTTPException(
                status_code=400, detail="Section ID is required for saved sections."
            )
        section = db.get(ActSection, payload.section_id)
        if not section:
            raise HTTPException(status_code=404, detail="Section not found.")
        if payload.act_id and payload.act_id != section.act_id:
            raise HTTPException(status_code=400, detail="Section does not belong to Act.")
        return {"act_id": section.act_id, "section_id": section.id, "reference_id": None}

    if not payload.reference_id:
        raise HTTPException(
            status_code=400, detail="Reference ID is required for saved references."
        )
    reference = db.get(LegalReference, payload.reference_id)
    if not reference:
        raise HTTPException(status_code=404, detail="Reference not found.")
    if payload.act_id and payload.act_id != reference.source_act_id:
        raise HTTPException(status_code=400, detail="Reference does not belong to Act.")
    if payload.section_id and payload.section_id != reference.source_section_id:
        raise HTTPException(status_code=400, detail="Reference does not belong to section.")
    return {
        "act_id": reference.source_act_id,
        "section_id": reference.source_section_id,
        "reference_id": reference.id,
    }


def _duplicate_saved_item(
    db: Session,
    user_id: str,
    item_type: SavedItemType,
    values: dict[str, str | None],
) -> SavedItem | None:
    query = db.query(SavedItem).filter(
        SavedItem.user_id == user_id,
        SavedItem.item_type == item_type,
    )
    if item_type == SavedItemType.ACT:
        return query.filter(SavedItem.act_id == values["act_id"]).first()
    if item_type == SavedItemType.SECTION:
        return query.filter(SavedItem.section_id == values["section_id"]).first()
    return query.filter(SavedItem.reference_id == values["reference_id"]).first()


def _mapped_status_filter(mapped_status: str):
    mapped_expression = or_(
        LegalReference.target_act_id.is_not(None),
        LegalReference.target_section_id.is_not(None),
    )
    if mapped_status == "mapped":
        return SavedItem.reference.has(mapped_expression)
    return SavedItem.reference.has(
        and_(
            LegalReference.target_act_id.is_(None),
            LegalReference.target_section_id.is_(None),
        )
    )


def _counts_by_type(db: Session, user_id: str) -> dict[str, int]:
    return {
        item_type.value: db.query(SavedItem)
        .filter(SavedItem.user_id == user_id, SavedItem.item_type == item_type)
        .count()
        for item_type in SavedItemType
    }
