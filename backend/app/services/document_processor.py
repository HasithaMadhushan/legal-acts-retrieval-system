from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.roles import ParserName, ProcessingJobStatus, ProcessingStatus, VerificationStatus
from app.db.session import SessionLocal
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.models.legal_reference import LegalReference
from app.models.processing_job import ProcessingJob
from app.models.user import User
from app.services.metadata_extractor import ExtractedMetadata, extract_metadata
from app.services.pdf_parser.base import PdfExtractionError, PdfParser
from app.services.pdf_parser.docling_parser import DoclingParser
from app.services.pdf_parser.pymupdf_parser import PyMuPdfParser
from app.services.reference_extractor import (
    ReferenceDraft,
    extract_references,
    summarize_references,
)
from app.services.reference_mapper import map_references, summarize_mapping
from app.services.section_segmenter import segment_act_text
from app.services.storage import get_storage
from app.services.text_cleaner import clean_text, normalize_for_search

logger = get_logger(__name__)

# Sections/references an Admin has explicitly decided on are "locked": they and any
# rows tied to them are frozen during reprocessing instead of being regenerated, so
# verification work is never silently lost when an Act is reprocessed.
_LOCKED_VERIFICATION_STATUSES = {VerificationStatus.VERIFIED, VerificationStatus.REJECTED}


def process_act(db: Session, act: LegalAct, user: User) -> ProcessingJob:
    """Run processing synchronously to completion in the current session.

    Kept for direct/script use. The `/acts/{id}/process` API route instead uses
    `create_processing_job` + `run_processing_job` so the HTTP request can return
    immediately while the actual extraction work runs as a background task.
    """
    job = create_processing_job(db, act, user)
    return _execute_processing_job(db, job, act)


def create_processing_job(db: Session, act: LegalAct, user: User) -> ProcessingJob:
    """Create a QUEUED processing job and mark the Act as PROCESSING.

    This is deliberately cheap (no PDF parsing) so it can run synchronously
    inside a request handler; the actual work happens in `run_processing_job`.
    """
    job = ProcessingJob(
        act_id=act.id,
        status=ProcessingJobStatus.QUEUED,
        current_step="Queued",
        progress_percent=0,
        created_by_user_id=user.id,
        summary_json={
            "previous_processing_status": act.processing_status.value,
            "warnings": [],
            "errors": [],
        },
    )
    act.processing_status = ProcessingStatus.PROCESSING
    act.processing_error = None
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def run_processing_job(job_id: str) -> None:
    """Execute a previously-queued processing job in its own DB session.

    Designed to be scheduled as a FastAPI `BackgroundTask`, which runs after the
    HTTP response has already been sent, so it cannot reuse the request-scoped
    session (which is closed by then).
    """
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        if job is None:
            logger.error("processing_job_not_found", job_id=job_id)
            return
        act = db.get(LegalAct, job.act_id)
        if act is None:
            job.status = ProcessingJobStatus.FAILED
            job.error_message = "The Act associated with this job no longer exists."
            job.completed_at = datetime.utcnow()
            db.commit()
            return
        _execute_processing_job(db, job, act)


def _execute_processing_job(db: Session, job: ProcessingJob, act: LegalAct) -> ProcessingJob:
    settings = get_settings()
    parser, parser_requested, selection_warnings = _select_parser(settings)
    previous_processing_status = _processing_status_from_job(job)
    summary: dict[str, object] = {
        "parser_requested": parser_requested,
        "parser_used": getattr(parser, "parser_name", ParserName.UNKNOWN.value),
        "page_count": None,
        "extracted_character_count": 0,
        "warnings": selection_warnings.copy(),
        "errors": [],
        "sections_created": 0,
        "references_created": 0,
    }
    job.status = ProcessingJobStatus.RUNNING
    job.current_step = "Starting processing"
    job.progress_percent = 5
    job.started_at = datetime.utcnow()
    job.summary_json = summary
    db.commit()
    db.refresh(job)
    db.refresh(act)

    try:
        job.current_step = "Extracting PDF text"
        job.progress_percent = 20
        db.flush()

        local_pdf_path = get_storage().ensure_local_path(act.stored_file_path)
        parsed = parser.extract(str(local_pdf_path))
        raw_text = parsed.full_text
        cleaned_text = clean_text(raw_text)
        warnings = _unique_strings([*selection_warnings, *parsed.warnings])
        extracted_character_count = len(cleaned_text)
        summary.update(
            {
                "parser_used": parsed.parser_name,
                "page_count": parsed.page_count,
                "extracted_character_count": extracted_character_count,
                "warnings": warnings,
            }
        )
        if not cleaned_text.strip():
            message = (
                "No extractable text was found. The PDF may be scanned or image-only; "
                "OCR is disabled for this MVP."
            )
            raise PdfExtractionError(
                message,
                parser_name=parsed.parser_name,
                page_count=parsed.page_count,
                extracted_character_count=extracted_character_count,
                warnings=_unique_strings([*warnings, message]),
            )

        job.current_step = "Extracting metadata"
        job.progress_percent = 40
        metadata = extract_metadata(cleaned_text, act.source_file_name)
        metadata_summary = _metadata_summary(metadata)
        if previous_processing_status in {ProcessingStatus.PROCESSED, ProcessingStatus.VERIFIED}:
            metadata_summary["preserved_fields"] = _metadata_field_names()
        else:
            metadata_summary["applied_fields"] = _apply_extracted_metadata(act, metadata)
        summary["metadata"] = metadata_summary

        act.page_count = parsed.page_count
        act.raw_text = raw_text
        act.parser_used = _parser_name(parsed.parser_name)

        job.current_step = "Segmenting sections"
        job.progress_percent = 60
        segmentation = segment_act_text(cleaned_text)
        segmentation_summary = segmentation.summary

        existing_sections = db.query(ActSection).filter(ActSection.act_id == act.id).all()
        existing_references = (
            db.query(LegalReference).filter(LegalReference.source_act_id == act.id).all()
        )

        locked_reference_ids = {
            reference.id
            for reference in existing_references
            if reference.verification_status in _LOCKED_VERIFICATION_STATUSES
        }
        locked_section_ids = {
            section.id
            for section in existing_sections
            if section.verification_status in _LOCKED_VERIFICATION_STATUSES
        }
        locked_section_ids.update(
            reference.source_section_id
            for reference in existing_references
            if reference.id in locked_reference_ids and reference.source_section_id
        )

        preserved_sections = [
            section for section in existing_sections if section.id in locked_section_ids
        ]
        preserved_section_keys = {
            _section_key(section.section_number, section.section_path)
            for section in preserved_sections
        }

        # A reference is preserved if it is itself locked, or if it lives on a
        # preserved section (frozen sections keep every reference untouched so the
        # section/reference pair never ends up in an inconsistent partial state).
        references_to_delete_ids = [
            reference.id
            for reference in existing_references
            if reference.id not in locked_reference_ids
            and reference.source_section_id not in locked_section_ids
        ]
        sections_to_delete_ids = [
            section.id for section in existing_sections if section.id not in locked_section_ids
        ]
        preserved_reference_count = len(existing_references) - len(references_to_delete_ids)

        if references_to_delete_ids:
            db.execute(delete(LegalReference).where(LegalReference.id.in_(references_to_delete_ids)))
        if sections_to_delete_ids:
            db.execute(delete(ActSection).where(ActSection.id.in_(sections_to_delete_ids)))
        db.flush()

        if preserved_sections:
            segmentation_warnings = segmentation_summary.get("warnings")
            if not isinstance(segmentation_warnings, list):
                segmentation_warnings = []
            segmentation_warnings.append(
                f"{len(preserved_sections)} verified/rejected section(s) were preserved and "
                "excluded from reprocessing."
            )
            segmentation_summary["warnings"] = _unique_strings(
                [warning for warning in segmentation_warnings if isinstance(warning, str)]
            )
            segmentation_summary["sections_preserved"] = len(preserved_sections)
        summary["segmentation"] = segmentation_summary

        section_drafts = segmentation.sections
        sections: list[ActSection] = []
        for draft in section_drafts:
            if _section_key(draft.section_number, draft.section_path) in preserved_section_keys:
                continue
            section = ActSection(
                act_id=act.id,
                section_number=draft.section_number,
                section_path=draft.section_path,
                heading=draft.heading,
                section_type=draft.section_type,
                text=draft.text,
                normalized_text=draft.normalized_text,
                page_start=draft.page_start,
                page_end=draft.page_end,
                sort_order=draft.sort_order,
                verification_status=VerificationStatus.PENDING,
            )
            db.add(section)
            sections.append(section)
        db.flush()

        job.current_step = "Extracting and mapping references"
        job.progress_percent = 80
        reference_drafts: list[ReferenceDraft] = []
        references: list[LegalReference] = []
        for section in sections:
            for draft in extract_references(section.text):
                reference_drafts.append(draft)
                reference = LegalReference(
                    source_act_id=act.id,
                    source_section_id=section.id,
                    raw_reference_text=draft.raw_reference_text,
                    context_snippet=draft.context_snippet,
                    relationship_type=draft.relationship_type,
                    target_act_title_raw=draft.target_act_title_raw,
                    target_act_number=draft.target_act_number,
                    target_act_year=draft.target_act_year,
                    target_section_number=draft.target_section_number,
                    target_section_path=draft.target_section_path,
                    confidence_score=draft.confidence_score,
                    extraction_method=draft.extraction_method,
                    verification_status=draft.verification_status,
                )
                references.append(reference)

        mapping_results = map_references(db, act, references)
        for result in mapping_results:
            db.add(result.reference)

        reference_summary = summarize_references(reference_drafts)
        if preserved_reference_count:
            reference_warnings = reference_summary.get("warnings")
            if not isinstance(reference_warnings, list):
                reference_warnings = []
            reference_warnings.append(
                f"{preserved_reference_count} reference(s) were preserved (verified/rejected, "
                "or tied to a preserved section) and excluded from reprocessing."
            )
            reference_summary["warnings"] = _unique_strings(
                [warning for warning in reference_warnings if isinstance(warning, str)]
            )
            reference_summary["references_preserved"] = preserved_reference_count
        summary["references"] = reference_summary
        summary["mapping"] = summarize_mapping(mapping_results)

        act.normalized_title = normalize_for_search(act.title)
        act.processing_status = ProcessingStatus.PROCESSED
        job.status = ProcessingJobStatus.COMPLETED
        job.current_step = "Completed"
        job.progress_percent = 100
        job.completed_at = datetime.utcnow()
        summary.update(
            {
                "sections_created": len(sections),
                "sections_preserved": len(preserved_sections),
                "references_created": len(references),
                "references_preserved": preserved_reference_count,
                "errors": [],
            }
        )
        job.summary_json = summary
        db.commit()
        db.refresh(job)
        logger.info(
            "processing_job_completed",
            job_id=job.id,
            act_id=act.id,
            sections_created=summary["sections_created"],
            references_created=summary["references_created"],
        )
        return job
    except Exception as exc:
        db.rollback()
        error_message = str(exc) or "PDF processing failed."
        if isinstance(exc, PdfExtractionError):
            summary.update(
                {
                    "parser_used": exc.parser_name,
                    "page_count": exc.page_count,
                    "extracted_character_count": exc.extracted_character_count or 0,
                    "warnings": _unique_strings(
                        [*_as_string_list(summary.get("warnings")), *exc.warnings]
                    ),
                }
            )
        summary["errors"] = _unique_strings(
            [*_as_string_list(summary.get("errors")), error_message]
        )

        failed_act = db.get(LegalAct, act.id)
        failed_job = db.get(ProcessingJob, job.id)
        if failed_act is None or failed_job is None:
            raise

        page_count = summary.get("page_count")
        if isinstance(page_count, int):
            failed_act.page_count = page_count
        failed_act.parser_used = _parser_name(
            str(summary.get("parser_used") or ParserName.UNKNOWN.value)
        )
        failed_act.processing_status = ProcessingStatus.FAILED
        failed_act.processing_error = error_message
        failed_job.status = ProcessingJobStatus.FAILED
        failed_job.current_step = "Failed"
        failed_job.progress_percent = 100
        failed_job.completed_at = datetime.utcnow()
        failed_job.error_message = error_message
        failed_job.summary_json = summary
        db.commit()
        db.refresh(failed_job)
        logger.warning(
            "processing_job_failed",
            job_id=failed_job.id,
            act_id=failed_act.id,
            error=error_message,
        )
        return failed_job


def _select_parser(settings) -> tuple[PdfParser, str, list[str]]:
    requested = settings.doc_parser_primary.strip().lower()
    warnings: list[str] = []

    if requested == "docling":
        if settings.docling_enabled:
            return (
                DoclingParser(timeout_seconds=settings.docling_timeout_seconds),
                requested,
                warnings,
            )
        warnings.append("Docling was requested, but DOCLING_ENABLED=false; PyMuPDF was used.")
        return PyMuPdfParser(), requested, warnings

    if requested == "ocr":
        warnings.append("OCR parsing is not enabled for this MVP; PyMuPDF was used.")
        return PyMuPdfParser(), requested, warnings

    if requested not in {"", "pymupdf"}:
        warnings.append(f"Unknown DOC_PARSER_PRIMARY={requested!r}; PyMuPDF was used.")

    return PyMuPdfParser(), requested or "pymupdf", warnings


def _processing_status_from_job(job: ProcessingJob) -> ProcessingStatus:
    raw_value = job.summary_json.get("previous_processing_status") if job.summary_json else None
    try:
        return ProcessingStatus(raw_value)
    except ValueError:
        return ProcessingStatus.UPLOADED


def _parser_name(value: str) -> ParserName:
    try:
        return ParserName(value)
    except ValueError:
        return ParserName.UNKNOWN


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _apply_extracted_metadata(act: LegalAct, metadata: ExtractedMetadata) -> list[str]:
    act.title = metadata.title
    act.normalized_title = metadata.normalized_title
    act.act_number = metadata.act_number
    act.year = metadata.year
    act.certification_date = metadata.certification_date
    act.publication_date = metadata.publication_date
    return [
        field
        for field, value in {
            "title": metadata.title,
            "act_number": metadata.act_number,
            "year": metadata.year,
            "certification_date": metadata.certification_date,
            "publication_date": metadata.publication_date,
        }.items()
        if value is not None
    ]


def _metadata_summary(metadata: ExtractedMetadata) -> dict[str, object]:
    return {
        "extracted": {
            "title": metadata.title,
            "normalized_title": metadata.normalized_title,
            "act_number": metadata.act_number,
            "year": metadata.year,
            "certification_date": _date_string(metadata.certification_date),
            "publication_date": _date_string(metadata.publication_date),
        },
        "confidence_score": metadata.confidence_score,
        "warnings": metadata.warnings or [],
        "applied_fields": [],
        "preserved_fields": [],
    }


def _metadata_field_names() -> list[str]:
    return [
        "title",
        "act_number",
        "year",
        "certification_date",
        "publication_date",
        "category",
        "source_name",
        "source_url",
    ]


def _date_string(value) -> str | None:
    return value.isoformat() if value else None


def _section_key(section_number: str, section_path: str | None) -> tuple[str, str | None]:
    return (section_number, section_path)


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value and value not in seen:
            unique.append(value)
            seen.add(value)
    return unique
