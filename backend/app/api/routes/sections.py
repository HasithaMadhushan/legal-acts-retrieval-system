from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.roles import UserRole, VerificationStatus
from app.db.session import get_db
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.models.user import User
from app.schemas.section import SectionRead, SectionUpdate
from app.services.text_cleaner import normalize_for_search

router = APIRouter(tags=["sections"])


@router.get("/acts/{act_id}/sections", response_model=list[SectionRead])
def list_sections(
    act_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ActSection]:
    if not db.get(LegalAct, act_id):
        raise HTTPException(status_code=404, detail="Act not found.")
    query = db.query(ActSection).filter(ActSection.act_id == act_id)
    if current_user.role == UserRole.GENERAL_USER:
        query = query.filter(ActSection.verification_status == VerificationStatus.VERIFIED)
    return query.order_by(ActSection.sort_order).all()


@router.get("/sections/{section_id}", response_model=SectionRead)
def get_section(
    section_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ActSection:
    section = db.get(ActSection, section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found.")
    if (
        current_user.role == UserRole.GENERAL_USER
        and section.verification_status != VerificationStatus.VERIFIED
    ):
        raise HTTPException(status_code=403, detail="Section is not available.")
    return section


@router.patch("/sections/{section_id}", response_model=SectionRead)
def update_section(
    section_id: str,
    payload: SectionUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ActSection:
    section = db.get(ActSection, section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found.")
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(section, key, value)
    if payload.text is not None:
        section.normalized_text = normalize_for_search(payload.text)
    db.commit()
    db.refresh(section)
    return section


@router.post("/sections/{section_id}/verify", response_model=SectionRead)
def verify_section(
    section_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ActSection:
    section = db.get(ActSection, section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found.")
    section.verification_status = VerificationStatus.VERIFIED
    db.commit()
    db.refresh(section)
    return section


@router.post("/sections/{section_id}/reject", response_model=SectionRead)
def reject_section(
    section_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ActSection:
    section = db.get(ActSection, section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found.")
    section.verification_status = VerificationStatus.REJECTED
    db.commit()
    db.refresh(section)
    return section
