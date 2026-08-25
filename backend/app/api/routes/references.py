
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.roles import ExtractionMethod, UserRole, VerificationStatus
from app.db.session import get_db
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.models.legal_reference import LegalReference
from app.models.mixins import utc_now
from app.models.user import User
from app.schemas.reference import LinkTargetRequest, ReferenceCreate, ReferenceRead, ReferenceUpdate

router = APIRouter(tags=["references"])


def _visible_reference_query(db: Session, current_user: User):
    query = db.query(LegalReference)
    if current_user.role == UserRole.GENERAL_USER:
        query = _general_user_reference_visibility(query)
    return query


@router.get("/acts/{act_id}/references", response_model=list[ReferenceRead])
def list_act_references(
    act_id: str,
    include_pending: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[LegalReference]:
    query = db.query(LegalReference).filter(LegalReference.source_act_id == act_id)
    if current_user.role == UserRole.GENERAL_USER:
        query = _general_user_reference_visibility(query)
    elif current_user.role == UserRole.LAWYER and not include_pending:
        query = query.filter(LegalReference.verification_status == VerificationStatus.VERIFIED)
    return query.order_by(LegalReference.created_at.desc()).all()


@router.get("/sections/{section_id}/references", response_model=list[ReferenceRead])
def list_section_references(
    section_id: str,
    include_pending: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[LegalReference]:
    query = db.query(LegalReference).filter(LegalReference.source_section_id == section_id)
    if current_user.role == UserRole.GENERAL_USER:
        query = _general_user_reference_visibility(query)
    elif current_user.role == UserRole.LAWYER and not include_pending:
        query = query.filter(LegalReference.verification_status == VerificationStatus.VERIFIED)
    return query.order_by(LegalReference.created_at.desc()).all()


@router.get("/references/{reference_id}", response_model=ReferenceRead)
def get_reference(
    reference_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LegalReference:
    reference = (
        _visible_reference_query(db, current_user)
        .filter(LegalReference.id == reference_id)
        .first()
    )
    if not reference:
        raise HTTPException(status_code=404, detail="Reference not found.")
    return reference


@router.post("/references", response_model=ReferenceRead, status_code=201)
def create_reference(
    payload: ReferenceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> LegalReference:
    _validate_source(db, payload.source_act_id, payload.source_section_id)
    _validate_target_links(db, payload.target_act_id, payload.target_section_id)
    reference = LegalReference(
        source_act_id=payload.source_act_id,
        source_section_id=payload.source_section_id,
        raw_reference_text=payload.raw_reference_text,
        context_snippet=payload.context_snippet,
        relationship_type=payload.relationship_type,
        target_act_title_raw=payload.target_act_title_raw,
        target_act_number=payload.target_act_number,
        target_act_year=payload.target_act_year,
        target_section_number=payload.target_section_number,
        target_section_path=payload.target_section_path,
        target_act_id=payload.target_act_id,
        target_section_id=payload.target_section_id,
        confidence_score=payload.confidence_score,
        extraction_method=ExtractionMethod.MANUAL,
        verification_status=payload.verification_status,
        notes=payload.notes,
    )
    _set_verification_metadata(reference, current_user)
    db.add(reference)
    db.commit()
    db.refresh(reference)
    return reference


@router.patch("/references/{reference_id}", response_model=ReferenceRead)
def update_reference(
    reference_id: str,
    payload: ReferenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> LegalReference:
    reference = db.get(LegalReference, reference_id)
    if not reference:
        raise HTTPException(status_code=404, detail="Reference not found.")
    update_data = payload.model_dump(exclude_unset=True)
    _validate_target_links(
        db,
        update_data.get("target_act_id", reference.target_act_id),
        update_data.get("target_section_id", reference.target_section_id),
    )
    for key, value in update_data.items():
        setattr(reference, key, value)
    if "verification_status" in update_data:
        _set_verification_metadata(reference, current_user)
    db.commit()
    db.refresh(reference)
    return reference


@router.post("/references/{reference_id}/verify", response_model=ReferenceRead)
def verify_reference(
    reference_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> LegalReference:
    reference = db.get(LegalReference, reference_id)
    if not reference:
        raise HTTPException(status_code=404, detail="Reference not found.")
    reference.verification_status = VerificationStatus.VERIFIED
    reference.verified_by_user_id = current_user.id
    reference.verified_at = utc_now()
    db.commit()
    db.refresh(reference)
    return reference


@router.post("/references/{reference_id}/reject", response_model=ReferenceRead)
def reject_reference(
    reference_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> LegalReference:
    reference = db.get(LegalReference, reference_id)
    if not reference:
        raise HTTPException(status_code=404, detail="Reference not found.")
    reference.verification_status = VerificationStatus.REJECTED
    reference.verified_by_user_id = current_user.id
    reference.verified_at = utc_now()
    db.commit()
    db.refresh(reference)
    return reference


@router.post("/references/{reference_id}/link-target", response_model=ReferenceRead)
def link_reference_target(
    reference_id: str,
    payload: LinkTargetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> LegalReference:
    reference = db.get(LegalReference, reference_id)
    if not reference:
        raise HTTPException(status_code=404, detail="Reference not found.")
    _validate_target_links(db, payload.target_act_id, payload.target_section_id)
    reference.target_act_id = payload.target_act_id
    reference.target_section_id = payload.target_section_id
    reference.notes = payload.notes
    if payload.target_act_id or payload.target_section_id:
        reference.verification_status = VerificationStatus.VERIFIED
        reference.verified_by_user_id = current_user.id
        reference.verified_at = utc_now()
    else:
        reference.verification_status = VerificationStatus.NEEDS_REVIEW
        reference.verified_by_user_id = None
        reference.verified_at = None
    db.commit()
    db.refresh(reference)
    return reference


def _validate_source(
    db: Session, source_act_id: str, source_section_id: str | None
) -> None:
    if not db.get(LegalAct, source_act_id):
        raise HTTPException(status_code=404, detail="Source Act not found.")
    if source_section_id:
        section = db.get(ActSection, source_section_id)
        if not section:
            raise HTTPException(status_code=404, detail="Source section not found.")
        if section.act_id != source_act_id:
            raise HTTPException(
                status_code=400,
                detail="Source section does not belong to the source Act.",
            )


def _validate_target_links(
    db: Session, target_act_id: str | None, target_section_id: str | None
) -> None:
    if target_act_id and not db.get(LegalAct, target_act_id):
        raise HTTPException(status_code=404, detail="Target Act not found.")
    if target_section_id:
        section = db.get(ActSection, target_section_id)
        if not section:
            raise HTTPException(status_code=404, detail="Target section not found.")
        if target_act_id and section.act_id != target_act_id:
            raise HTTPException(
                status_code=400,
                detail="Target section does not belong to the target Act.",
            )


def _set_verification_metadata(reference: LegalReference, current_user: User) -> None:
    if reference.verification_status in {
        VerificationStatus.VERIFIED,
        VerificationStatus.REJECTED,
    }:
        reference.verified_by_user_id = current_user.id
        reference.verified_at = utc_now()
    else:
        reference.verified_by_user_id = None
        reference.verified_at = None


def _general_user_reference_visibility(query):
    return query.filter(
        LegalReference.verification_status == VerificationStatus.VERIFIED,
        or_(
            LegalReference.target_act_id.is_not(None),
            LegalReference.target_section_id.is_not(None),
        ),
    )
