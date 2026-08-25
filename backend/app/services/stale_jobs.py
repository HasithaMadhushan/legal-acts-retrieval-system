from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.roles import ProcessingJobStatus, ProcessingStatus
from app.models.legal_act import LegalAct
from app.models.processing_job import ProcessingJob


def fail_stale_running_jobs(db: Session, older_than_minutes: int = 30) -> int:
    """Mark RUNNING jobs older than the cutoff as FAILED after a process restart."""
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=older_than_minutes)
    jobs = (
        db.query(ProcessingJob)
        .filter(
            ProcessingJob.status == ProcessingJobStatus.RUNNING,
            ProcessingJob.created_at < cutoff,
        )
        .all()
    )
    for job in jobs:
        job.status = ProcessingJobStatus.FAILED
        job.error_message = "interrupted by restart"
        job.completed_at = datetime.now(UTC).replace(tzinfo=None)
        job.current_step = "Interrupted by restart"
        act = db.get(LegalAct, job.act_id)
        if act is not None and act.processing_status == ProcessingStatus.PROCESSING:
            act.processing_status = ProcessingStatus.FAILED
            act.processing_error = "interrupted by restart"
    if jobs:
        db.commit()
    return len(jobs)
