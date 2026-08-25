from collections import Counter
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.roles import (
    ExtractionMethod,
    ProcessingJobStatus,
    ProcessingStatus,
    VerificationStatus,
)
from app.models.act_section import ActSection
from app.models.evaluation import EvaluationGoldReference, EvaluationRun
from app.models.legal_act import LegalAct
from app.models.legal_reference import LegalReference
from app.models.processing_job import ProcessingJob

EvaluationKey = tuple[str, str, str, str]


def calculate_metrics(
    *,
    gold_keys: set[tuple],
    predicted_keys: set[tuple],
) -> dict[str, float | int]:
    true_positives = len(gold_keys & predicted_keys)
    false_positives = len(predicted_keys - gold_keys)
    false_negatives = len(gold_keys - predicted_keys)
    precision = true_positives / (true_positives + false_positives) if predicted_keys else 0.0
    recall = true_positives / (true_positives + false_negatives) if gold_keys else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
    }


def calculate_section_segmentation_accuracy(
    *,
    expected_sections: set[str],
    detected_sections: set[str],
) -> float | None:
    if not expected_sections:
        return None
    return round(len(expected_sections & detected_sections) / len(expected_sections), 4)


def run_reference_evaluation(
    db: Session,
    *,
    run_name: str,
    act_id: str | None = None,
    section_segmentation_accuracy: float | None = None,
    extraction_mode: str | None = None,
) -> EvaluationRun:
    gold_query = db.query(EvaluationGoldReference)
    prediction_query = db.query(LegalReference)
    if act_id:
        gold_query = gold_query.filter(EvaluationGoldReference.act_id == act_id)
        prediction_query = prediction_query.filter(LegalReference.source_act_id == act_id)
    mode = (extraction_mode or "hybrid").strip().lower()
    if mode == "regex-only":
        prediction_query = prediction_query.filter(
            LegalReference.extraction_method == ExtractionMethod.REGEX
        )
    elif mode == "llm-only":
        prediction_query = prediction_query.filter(
            LegalReference.extraction_method == ExtractionMethod.LLM
        )

    gold = gold_query.all()
    predictions = prediction_query.all()
    gold_keys = {_gold_key(item) for item in gold}
    predicted_keys = {_prediction_key(item) for item in predictions}
    metrics = calculate_metrics(gold_keys=gold_keys, predicted_keys=predicted_keys)
    false_positive_keys = sorted(predicted_keys - gold_keys)
    false_negative_keys = sorted(gold_keys - predicted_keys)
    matched_keys = sorted(gold_keys & predicted_keys)
    if section_segmentation_accuracy is None:
        section_segmentation_accuracy = calculate_section_segmentation_accuracy(
            expected_sections={
                _normalize_text(
                    item.source_section.section_path or item.source_section.section_number
                )
                for item in gold
                if item.source_section
            },
            detected_sections={
                _normalize_text(
                    reference.source_section.section_path
                    or reference.source_section.section_number
                )
                for reference in predictions
                if reference.source_section
            },
        )
    run = EvaluationRun(
        run_name=run_name,
        act_id=act_id,
        section_segmentation_accuracy=section_segmentation_accuracy,
        total_gold_references=len(gold_keys),
        run_summary_json={
            "extraction_mode": mode,
            "gold_count": len(gold_keys),
            "predicted_count": len(predicted_keys),
            "matched": [_key_to_dict(key) for key in matched_keys[:100]],
            "false_positives": [_key_to_dict(key) for key in false_positive_keys[:100]],
            "false_negatives": [_key_to_dict(key) for key in false_negative_keys[:100]],
            "mismatch_counts": {
                "matched": len(matched_keys),
                "false_positives": len(false_positive_keys),
                "false_negatives": len(false_negative_keys),
            },
        },
        **metrics,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def metrics_summary(db: Session) -> dict[str, Any]:
    processing_counts = {
        status.value: db.query(LegalAct).filter(LegalAct.processing_status == status).count()
        for status in ProcessingStatus
    }
    section_status_counts = {
        status.value: db.query(ActSection)
        .filter(ActSection.verification_status == status)
        .count()
        for status in VerificationStatus
    }
    reference_status_counts = {
        status.value: db.query(LegalReference)
        .filter(LegalReference.verification_status == status)
        .count()
        for status in VerificationStatus
    }
    mapped_references = (
        db.query(LegalReference)
        .filter(
            or_(
                LegalReference.target_act_id.is_not(None),
                LegalReference.target_section_id.is_not(None),
            )
        )
        .count()
    )
    total_references = db.query(LegalReference).count()
    processing_job_counts = {
        status.value: db.query(ProcessingJob).filter(ProcessingJob.status == status).count()
        for status in ProcessingJobStatus
    }
    latest_jobs = (
        db.query(ProcessingJob)
        .order_by(ProcessingJob.created_at.desc())
        .limit(10)
        .all()
    )
    return {
        "document_counts": {
            "total": db.query(LegalAct).count(),
            "uploaded": processing_counts.get(ProcessingStatus.UPLOADED.value, 0),
            "processing": processing_counts.get(ProcessingStatus.PROCESSING.value, 0),
            "processed": processing_counts.get(ProcessingStatus.PROCESSED.value, 0),
            "failed": processing_counts.get(ProcessingStatus.FAILED.value, 0),
            "verified": processing_counts.get(ProcessingStatus.VERIFIED.value, 0),
        },
        "section_counts": {
            "total": db.query(ActSection).count(),
            **_status_alias_counts(section_status_counts),
        },
        "reference_counts": {
            "total": total_references,
            **_status_alias_counts(reference_status_counts),
            "mapped": mapped_references,
            "unresolved": total_references - mapped_references,
        },
        "processing_job_counts": processing_job_counts,
        "latest_processing_messages": [_job_messages(job) for job in latest_jobs],
        "latest_evaluation_runs": [
            {
                "id": run.id,
                "run_name": run.run_name,
                "precision": run.precision,
                "recall": run.recall,
                "f1_score": run.f1_score,
                "created_at": run.created_at.isoformat(),
            }
            for run in (
                db.query(EvaluationRun)
                .order_by(EvaluationRun.created_at.desc())
                .limit(5)
                .all()
            )
        ],
    }


def _gold_key(item: EvaluationGoldReference) -> EvaluationKey:
    return (
        _normalize_text(item.expected_raw_text),
        _normalize_text(item.expected_relationship_type).upper(),
        _normalize_text(item.expected_target_act_title),
        _normalize_text(item.expected_target_section_number),
    )


def _prediction_key(item: LegalReference) -> EvaluationKey:
    return (
        _normalize_text(item.raw_reference_text),
        item.relationship_type.value.upper(),
        _normalize_text(
            item.target_act_title_raw or (item.target_act.title if item.target_act else None)
        ),
        _normalize_text(item.target_section_number or item.target_section_path),
    )


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def _key_to_dict(key: EvaluationKey) -> dict[str, str]:
    raw_text, relationship_type, target_act_title, target_section = key
    return {
        "raw_text": raw_text,
        "relationship_type": relationship_type,
        "target_act_title": target_act_title,
        "target_section": target_section,
    }


def _status_alias_counts(counts: dict[str, int]) -> dict[str, int]:
    return {
        "pending": counts.get(VerificationStatus.PENDING.value, 0),
        "needs_review": counts.get(VerificationStatus.NEEDS_REVIEW.value, 0),
        "verified": counts.get(VerificationStatus.VERIFIED.value, 0),
        "rejected": counts.get(VerificationStatus.REJECTED.value, 0),
    }


def _job_messages(job: ProcessingJob) -> dict[str, Any]:
    summary = job.summary_json or {}
    warnings = _collect_messages(summary, "warnings")
    errors = _collect_messages(summary, "errors")
    return {
        "job_id": job.id,
        "act_id": job.act_id,
        "status": job.status.value,
        "current_step": job.current_step,
        "warnings": warnings[:10],
        "errors": errors[:10],
        "created_at": job.created_at.isoformat(),
    }


def _collect_messages(value: Any, key: str) -> list[str]:
    messages: list[str] = []
    if isinstance(value, dict):
        maybe_messages = value.get(key)
        if isinstance(maybe_messages, list):
            messages.extend(str(item) for item in maybe_messages if item)
        for nested in value.values():
            messages.extend(_collect_messages(nested, key))
    elif isinstance(value, list):
        for item in value:
            messages.extend(_collect_messages(item, key))
    return _unique(messages)


def _unique(values: list[str]) -> list[str]:
    return list(Counter(values).keys())
