from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.roles import ParserName, ProcessingStatus
from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class LegalAct(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "legal_acts"

    title: Mapped[str] = mapped_column(String(500), index=True, nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(500), index=True, nullable=False)
    act_number: Mapped[str | None] = mapped_column(String(50), index=True)
    year: Mapped[int | None] = mapped_column(Integer, index=True)
    certification_date: Mapped[date | None] = mapped_column(Date)
    publication_date: Mapped[date | None] = mapped_column(Date)
    category: Mapped[str | None] = mapped_column(String(255))
    source_name: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    source_file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    stored_file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer)
    mime_type: Mapped[str | None] = mapped_column(String(255))
    file_sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    raw_text: Mapped[str | None] = mapped_column(Text)
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status"),
        default=ProcessingStatus.UPLOADED,
        index=True,
        nullable=False,
    )
    parser_used: Mapped[ParserName] = mapped_column(
        Enum(ParserName, name="parser_name"), default=ParserName.UNKNOWN, nullable=False
    )
    processing_error: Mapped[str | None] = mapped_column(Text)
    uploaded_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(default=utc_now, index=True, nullable=False)
    extraction_artifact_key: Mapped[str | None] = mapped_column(String(1000))
    extraction_artifact_sha256: Mapped[str | None] = mapped_column(String(64))
    extraction_schema_version: Mapped[str | None] = mapped_column(String(32))
    extraction_created_at: Mapped[datetime | None] = mapped_column(DateTime)

    uploaded_by = relationship("User", back_populates="uploaded_acts")
    sections = relationship("ActSection", back_populates="act", cascade="all, delete-orphan")
    source_references = relationship(
        "LegalReference",
        back_populates="source_act",
        foreign_keys="LegalReference.source_act_id",
        cascade="all, delete-orphan",
    )
