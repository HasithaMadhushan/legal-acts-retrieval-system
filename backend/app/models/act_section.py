from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.roles import EmbeddingStatus, SectionType, VerificationStatus
from app.db.base import Base
from app.db.types import embedding_type
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ActSection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "act_sections"

    act_id: Mapped[str] = mapped_column(ForeignKey("legal_acts.id"), index=True, nullable=False)
    section_number: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    section_path: Mapped[str | None] = mapped_column(String(100), index=True)
    heading: Mapped[str | None] = mapped_column(String(500))
    section_type: Mapped[SectionType] = mapped_column(
        Enum(SectionType, name="section_type"), default=SectionType.SECTION, nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    parent_section_id: Mapped[str | None] = mapped_column(ForeignKey("act_sections.id"))
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status"),
        default=VerificationStatus.PENDING,
        index=True,
        nullable=False,
    )
    embedding: Mapped[list[float] | None] = mapped_column(embedding_type, nullable=True)
    embedding_provider: Mapped[str | None] = mapped_column(String(64))
    embedding_model: Mapped[str | None] = mapped_column(String(255))
    embedding_dimension: Mapped[int | None] = mapped_column(Integer)
    embedding_source_hash: Mapped[str | None] = mapped_column(String(64))
    embedding_status: Mapped[EmbeddingStatus] = mapped_column(
        Enum(EmbeddingStatus, name="embedding_status"),
        default=EmbeddingStatus.PENDING,
        nullable=False,
    )
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime)
    embedding_error: Mapped[str | None] = mapped_column(Text)

    act = relationship("LegalAct", back_populates="sections")
    parent_section = relationship("ActSection", remote_side="ActSection.id")
