from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.roles import ProcessingJobStatus
from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ProcessingJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "processing_jobs"

    act_id: Mapped[str] = mapped_column(ForeignKey("legal_acts.id"), index=True, nullable=False)
    status: Mapped[ProcessingJobStatus] = mapped_column(
        Enum(ProcessingJobStatus, name="processing_job_status"),
        default=ProcessingJobStatus.QUEUED,
        nullable=False,
    )
    current_step: Mapped[str] = mapped_column(String(255), default="Queued", nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(Text)
    summary_json: Mapped[dict | None] = mapped_column(JSON)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))

    act = relationship("LegalAct")
    created_by = relationship("User")
