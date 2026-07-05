from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.roles import ExtractionMethod, RelationshipType, VerificationStatus
from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class LegalReference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "legal_references"

    source_act_id: Mapped[str] = mapped_column(
        ForeignKey("legal_acts.id"), index=True, nullable=False
    )
    source_section_id: Mapped[str | None] = mapped_column(ForeignKey("act_sections.id"), index=True)
    raw_reference_text: Mapped[str] = mapped_column(String(1000), nullable=False)
    context_snippet: Mapped[str] = mapped_column(Text, nullable=False)
    relationship_type: Mapped[RelationshipType] = mapped_column(
        Enum(RelationshipType, name="relationship_type"),
        default=RelationshipType.UNKNOWN,
        index=True,
        nullable=False,
    )
    target_act_title_raw: Mapped[str | None] = mapped_column(String(500))
    target_act_number: Mapped[str | None] = mapped_column(String(50))
    target_act_year: Mapped[int | None]
    target_section_number: Mapped[str | None] = mapped_column(String(50))
    target_section_path: Mapped[str | None] = mapped_column(String(100))
    target_act_id: Mapped[str | None] = mapped_column(ForeignKey("legal_acts.id"), index=True)
    target_section_id: Mapped[str | None] = mapped_column(ForeignKey("act_sections.id"), index=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.3, nullable=False)
    extraction_method: Mapped[ExtractionMethod] = mapped_column(
        Enum(ExtractionMethod, name="extraction_method"),
        default=ExtractionMethod.REGEX,
        nullable=False,
    )
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="reference_verification_status"),
        default=VerificationStatus.PENDING,
        index=True,
        nullable=False,
    )
    verified_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(Text)

    source_act = relationship(
        "LegalAct", back_populates="source_references", foreign_keys=[source_act_id]
    )
    source_section = relationship("ActSection", foreign_keys=[source_section_id])
    target_act = relationship("LegalAct", foreign_keys=[target_act_id])
    target_section = relationship("ActSection", foreign_keys=[target_section_id])
    verified_by = relationship("User", foreign_keys=[verified_by_user_id])
