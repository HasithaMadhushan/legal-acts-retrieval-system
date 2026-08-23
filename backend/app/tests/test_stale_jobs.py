from datetime import UTC, datetime, timedelta

from app.core.roles import ProcessingJobStatus, ProcessingStatus
from app.db.session import SessionLocal
from app.models.legal_act import LegalAct
from app.models.processing_job import ProcessingJob
from app.models.user import User
from app.services.document_processor import fail_stale_running_jobs
from app.services.text_cleaner import normalize_for_search


def _sha(tag: str) -> str:
    return (tag * 8)[:64]


def test_fail_stale_running_jobs_marks_job_and_act_failed():
    with SessionLocal() as db:
        admin = db.query(User).filter(User.email == "admin@example.com").one()
        act = LegalAct(
            title="Stale Processing Act",
            normalized_title=normalize_for_search("Stale Processing Act"),
            act_number="1",
            year=2020,
            source_file_name="stale.pdf",
            stored_file_path="stale.pdf",
            file_sha256=_sha("stale"),
            processing_status=ProcessingStatus.PROCESSING,
            uploaded_by_user_id=admin.id,
        )
        db.add(act)
        db.flush()
        job = ProcessingJob(
            act_id=act.id,
            status=ProcessingJobStatus.RUNNING,
            current_step="Extracting PDF text",
            progress_percent=20,
            started_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2),
            created_by_user_id=admin.id,
        )
        db.add(job)
        db.commit()
        job.created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=45)
        db.commit()
        act_id, job_id = act.id, job.id

        count = fail_stale_running_jobs(db, older_than_minutes=30)
        assert count == 1

        db.refresh(job)
        db.refresh(act)
        assert job.status == ProcessingJobStatus.FAILED
        assert job.error_message == "interrupted by restart"
        assert act.processing_status == ProcessingStatus.FAILED

    # Reprocess endpoint still accepts the failed Act.
    # (HTTP coverage lives in test_acts_crud; this asserts the row is retryable.)
    with SessionLocal() as db:
        act = db.get(LegalAct, act_id)
        job = db.get(ProcessingJob, job_id)
        assert act is not None and job is not None
        assert act.processing_status == ProcessingStatus.FAILED
