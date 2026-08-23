import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.config import get_settings
from app.core.roles import ProcessingStatus, UserRole, VerificationStatus
from app.db.session import get_db
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.models.legal_reference import LegalReference
from app.models.processing_job import ProcessingJob
from app.models.user import User
from app.schemas.legal_act import (
    LegalActBrowseRead,
    LegalActDetail,
    LegalActRead,
    LegalActUpdate,
    ProcessingJobRead,
    VerificationSummaryRead,
)
from app.services.document_processor import create_processing_job, run_processing_job
from app.services.storage import get_storage
from app.services.text_cleaner import normalize_for_search

router = APIRouter(prefix="/acts", tags=["acts"])

PDF_MIME_TYPES = {"application/pdf", "application/octet-stream", ""}
PDF_SIGNATURE = b"%PDF-"


@router.get("", response_model=list[LegalActRead])
def list_acts(
    year: int | None = None,
    status: ProcessingStatus | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[LegalAct]:
    query = db.query(LegalAct)
    if year:
        query = query.filter(LegalAct.year == year)
    if status:
        query = query.filter(LegalAct.processing_status == status)
    if current_user.role != UserRole.ADMIN:
        query = query.filter(
            LegalAct.processing_status.in_(
                [ProcessingStatus.PROCESSED, ProcessingStatus.VERIFIED]
            )
        )
    return query.order_by(LegalAct.uploaded_at.desc()).all()


def _browse_entry(db: Session, act: LegalAct) -> LegalActBrowseRead:
    verified_sections = (
        db.query(ActSection)
        .filter(
            ActSection.act_id == act.id,
            ActSection.verification_status == VerificationStatus.VERIFIED,
        )
        .count()
    )
    verified_references = (
        db.query(LegalReference)
        .filter(
            LegalReference.source_act_id == act.id,
            LegalReference.verification_status == VerificationStatus.VERIFIED,
        )
        .count()
    )
    last_verified_at = act.updated_at if act.processing_status == ProcessingStatus.VERIFIED else None
    return LegalActBrowseRead(
        **LegalActRead.model_validate(act).model_dump(),
        verified_section_count=verified_sections,
        verified_reference_count=verified_references,
        last_verified_at=last_verified_at,
    )


@router.get("/browse", response_model=list[LegalActBrowseRead])
def browse_acts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[LegalActBrowseRead]:
    acts = list_acts(db=db, current_user=current_user)
    return [_browse_entry(db, act) for act in acts]


@router.post("/upload", response_model=LegalActRead, status_code=201)
def upload_act(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    act_number: str | None = Form(default=None),
    year: int | None = Form(default=None),
    category: str | None = Form(default=None),
    source_name: str | None = Form(default=None),
    source_url: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> LegalAct:
    settings = get_settings()
    original_name = file.filename or "uploaded.pdf"
    if "/" in original_name or "\\" in original_name:
        raise HTTPException(status_code=400, detail="File name must not contain path separators.")

    source_name_safe = Path(original_name).name
    if source_name_safe in {"", ".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid file name.")
    if not source_name_safe.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    mime_type = file.content_type or ""
    if mime_type not in PDF_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Only PDF MIME types are allowed.")

    content = file.file.read()
    if not content.startswith(PDF_SIGNATURE):
        raise HTTPException(status_code=400, detail="Uploaded file content is not a valid PDF.")
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(status_code=413, detail="PDF exceeds configured upload size limit.")
    digest = hashlib.sha256(content).hexdigest()
    if db.query(LegalAct).filter(LegalAct.file_sha256 == digest).first():
        raise HTTPException(status_code=409, detail="This PDF has already been uploaded.")

    stored_name = f"{uuid4()}.pdf"
    stored_key = get_storage().save(stored_name, content)

    title_value = (title or "").strip() or source_name_safe.rsplit(".", 1)[0].replace("_", " ")
    act = LegalAct(
        title=title_value,
        normalized_title=normalize_for_search(title_value),
        act_number=(act_number or "").strip() or None,
        year=year,
        category=category,
        source_name=source_name,
        source_url=source_url,
        source_file_name=source_name_safe,
        stored_file_path=stored_key,
        file_size=len(content),
        mime_type=mime_type or "application/pdf",
        file_sha256=digest,
        uploaded_by_user_id=current_user.id,
    )
    db.add(act)
    db.commit()
    db.refresh(act)
    return act


@router.get("/{act_id}", response_model=LegalActDetail)
def get_act(
    act_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LegalAct:
    act = db.get(LegalAct, act_id)
    if not act:
        raise HTTPException(status_code=404, detail="Act not found.")
    if current_user.role != UserRole.ADMIN and act.processing_status not in {
        ProcessingStatus.PROCESSED,
        ProcessingStatus.VERIFIED,
    }:
        raise HTTPException(status_code=403, detail="Act is not available for this role.")
    return act


@router.patch("/{act_id}", response_model=LegalActRead)
def update_act(
    act_id: str,
    payload: LegalActUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> LegalAct:
    act = db.get(LegalAct, act_id)
    if not act:
        raise HTTPException(status_code=404, detail="Act not found.")
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(act, key, value)
    if "title" in update_data and payload.title:
        act.normalized_title = normalize_for_search(payload.title)
    db.commit()
    db.refresh(act)
    return act


@router.delete("/{act_id}")
def delete_act(
    act_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    act = db.get(LegalAct, act_id)
    if not act:
        raise HTTPException(status_code=404, detail="Act not found.")
    db.delete(act)
    db.commit()
    return {"detail": "Act deleted."}


@router.post("/{act_id}/process", response_model=ProcessingJobRead)
def process_uploaded_act(
    act_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ProcessingJob:
    """Queue PDF processing for an Act and return immediately.

    The actual extraction work (parsing, segmentation, reference extraction)
    happens in a background task after this response is sent, since it can take
    a while for large PDFs. Poll `GET /acts/{act_id}/processing-jobs` for
    progress and the final COMPLETED/FAILED result.
    """
    act = db.get(LegalAct, act_id)
    if not act:
        raise HTTPException(status_code=404, detail="Act not found.")
    job = create_processing_job(db, act, current_user)
    background_tasks.add_task(run_processing_job, job.id)
    return job


@router.get("/{act_id}/processing-jobs", response_model=list[ProcessingJobRead])
def list_processing_jobs(
    act_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[ProcessingJob]:
    if not db.get(LegalAct, act_id):
        raise HTTPException(status_code=404, detail="Act not found.")
    return (
        db.query(ProcessingJob)
        .filter(ProcessingJob.act_id == act_id)
        .order_by(ProcessingJob.created_at.desc())
        .all()
    )


@router.get("/{act_id}/verification-summary", response_model=VerificationSummaryRead)
def verification_summary(
    act_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> VerificationSummaryRead:
    if not db.get(LegalAct, act_id):
        raise HTTPException(status_code=404, detail="Act not found.")

    section_query = db.query(ActSection).filter(ActSection.act_id == act_id)
    reference_query = db.query(LegalReference).filter(LegalReference.source_act_id == act_id)
    return VerificationSummaryRead(
        act_id=act_id,
        total_sections=section_query.count(),
        pending_sections=section_query.filter(
            ActSection.verification_status == VerificationStatus.PENDING
        ).count(),
        needs_review_sections=section_query.filter(
            ActSection.verification_status == VerificationStatus.NEEDS_REVIEW
        ).count(),
        verified_sections=section_query.filter(
            ActSection.verification_status == VerificationStatus.VERIFIED
        ).count(),
        rejected_sections=section_query.filter(
            ActSection.verification_status == VerificationStatus.REJECTED
        ).count(),
        total_references=reference_query.count(),
        pending_references=reference_query.filter(
            LegalReference.verification_status == VerificationStatus.PENDING
        ).count(),
        needs_review_references=reference_query.filter(
            LegalReference.verification_status == VerificationStatus.NEEDS_REVIEW
        ).count(),
        verified_references=reference_query.filter(
            LegalReference.verification_status == VerificationStatus.VERIFIED
        ).count(),
        rejected_references=reference_query.filter(
            LegalReference.verification_status == VerificationStatus.REJECTED
        ).count(),
        mapped_references=reference_query.filter(
            or_(
                LegalReference.target_act_id.is_not(None),
                LegalReference.target_section_id.is_not(None),
            )
        ).count(),
        unresolved_references=reference_query.filter(
            LegalReference.target_act_id.is_(None),
            LegalReference.target_section_id.is_(None),
        ).count(),
    )
