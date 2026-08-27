import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import delete, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.roles import ProcessingJobStatus, ProcessingStatus, UserRole, VerificationStatus
from app.db.session import get_db
from app.models.act_section import ActSection
from app.models.evaluation import EvaluationGoldReference, EvaluationRun
from app.models.legal_act import LegalAct
from app.models.legal_reference import LegalReference
from app.models.processing_job import ProcessingJob
from app.models.reading_history import ReadingHistoryItem
from app.models.saved_item import SavedItem
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
from app.services.extraction_artifact import (
    collect_artifact_pointers,
    load_extraction_artifact_view,
)
from app.services.storage import get_storage
from app.services.text_cleaner import normalize_for_search

router = APIRouter(prefix="/acts", tags=["acts"])
logger = get_logger(__name__)

PDF_MIME_TYPES = {"application/pdf", "application/octet-stream", ""}
PDF_SIGNATURE = b"%PDF-"
ACT_REFERENCED_DETAIL = "Act is referenced by other Acts and cannot be deleted."
ACT_PROCESSING_DETAIL = "Act cannot be deleted while processing is queued or running."
ACT_DELETE_CONFLICT = f"{ACT_REFERENCED_DETAIL} {ACT_PROCESSING_DETAIL}"


def _validate_upload_filename(original_name: str) -> str:
    if "/" in original_name or "\\" in original_name:
        raise HTTPException(status_code=400, detail="File name must not contain path separators.")
    source_name_safe = Path(original_name).name
    if source_name_safe in {"", ".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid file name.")
    if not source_name_safe.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
    return source_name_safe


def _read_upload_with_digest(file: UploadFile, limit: int) -> tuple[bytes, str]:
    hasher = hashlib.sha256()
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = file.file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(status_code=413, detail="PDF exceeds configured upload size limit.")
        hasher.update(chunk)
        chunks.append(chunk)
    return b"".join(chunks), hasher.hexdigest()


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
    last_verified_at = (
        act.updated_at if act.processing_status == ProcessingStatus.VERIFIED else None
    )
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


@router.post(
    "/upload",
    response_model=LegalActRead,
    status_code=201,
    responses={409: {"description": "Duplicate PDF already uploaded"}},
)
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
    source_name_safe = _validate_upload_filename(file.filename or "uploaded.pdf")
    mime_type = file.content_type or ""
    if mime_type not in PDF_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Only PDF MIME types are allowed.")

    content, digest = _read_upload_with_digest(file, settings.max_upload_size_bytes)
    if not content.startswith(PDF_SIGNATURE):
        raise HTTPException(status_code=400, detail="Uploaded file content is not a valid PDF.")
    if db.query(LegalAct).filter(LegalAct.file_sha256 == digest).first():
        raise HTTPException(status_code=409, detail="This PDF has already been uploaded.")

    stored_key = get_storage().save(f"{uuid4()}.pdf", content)
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
) -> LegalActDetail:
    act = db.get(LegalAct, act_id)
    if not act:
        raise HTTPException(status_code=404, detail="Act not found.")
    if current_user.role != UserRole.ADMIN and act.processing_status not in {
        ProcessingStatus.PROCESSED,
        ProcessingStatus.VERIFIED,
    }:
        raise HTTPException(status_code=403, detail="Act is not available for this role.")
    detail = LegalActDetail.model_validate(act)
    return detail.model_copy(
        update={"extraction_artifact": load_extraction_artifact_view(get_storage(), act)}
    )


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


@router.delete(
    "/{act_id}",
    responses={409: {"description": ACT_DELETE_CONFLICT}},
)
def delete_act(
    act_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    act = (
        db.query(LegalAct)
        .filter(LegalAct.id == act_id)
        .with_for_update()
        .one_or_none()
    )
    if not act:
        raise HTTPException(status_code=404, detail="Act not found.")
    if _has_active_processing(db, act_id):
        raise HTTPException(status_code=409, detail=ACT_PROCESSING_DETAIL)
    section_ids = [
        row[0] for row in db.query(ActSection.id).filter(ActSection.act_id == act_id)
    ]
    incoming_filter = LegalReference.target_act_id == act_id
    if section_ids:
        incoming_filter = or_(
            incoming_filter,
            LegalReference.target_section_id.in_(section_ids),
        )
    incoming = (
        db.query(LegalReference)
        .filter(
            incoming_filter,
            LegalReference.source_act_id != act_id,
        )
        .first()
    )
    if incoming:
        raise HTTPException(status_code=409, detail=ACT_REFERENCED_DETAIL)
    jobs = db.query(ProcessingJob).filter(ProcessingJob.act_id == act_id).all()
    storage_keys = [act.stored_file_path, *collect_artifact_pointers(act, jobs)]
    try:
        reference_ids = [
            row[0]
            for row in db.query(LegalReference.id).filter(
                LegalReference.source_act_id == act_id
            )
        ]
        saved_item_filter = SavedItem.act_id == act_id
        if section_ids:
            saved_item_filter = or_(
                saved_item_filter,
                SavedItem.section_id.in_(section_ids),
            )
        if reference_ids:
            saved_item_filter = or_(
                saved_item_filter,
                SavedItem.reference_id.in_(reference_ids),
            )
        db.execute(delete(SavedItem).where(saved_item_filter))
        db.execute(delete(ReadingHistoryItem).where(ReadingHistoryItem.act_id == act_id))
        db.execute(
            delete(EvaluationGoldReference).where(EvaluationGoldReference.act_id == act_id)
        )
        db.execute(delete(EvaluationRun).where(EvaluationRun.act_id == act_id))
        db.execute(delete(ProcessingJob).where(ProcessingJob.act_id == act_id))
        db.execute(delete(LegalReference).where(LegalReference.source_act_id == act_id))
        db.execute(delete(ActSection).where(ActSection.act_id == act_id))
        db.delete(act)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=ACT_REFERENCED_DETAIL) from None
    _best_effort_delete_storage(storage_keys)
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


def _has_active_processing(db: Session, act_id: str) -> bool:
    return (
        db.query(ProcessingJob.id)
        .filter(
            ProcessingJob.act_id == act_id,
            ProcessingJob.status.in_(
                (ProcessingJobStatus.QUEUED, ProcessingJobStatus.RUNNING)
            ),
        )
        .first()
        is not None
    )


def _best_effort_delete_storage(stored_keys: list[str]) -> None:
    storage = get_storage()
    for stored_key in stored_keys:
        try:
            storage.delete(stored_key)
        except Exception:
            logger.warning("storage_delete_failed", stored_key=stored_key)
