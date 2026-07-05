from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.roles import RelationshipType
from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class EvaluationGoldReference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_gold_references"

    act_id: Mapped[str | None] = mapped_column(ForeignKey("legal_acts.id"), index=True)
    source_section_id: Mapped[str | None] = mapped_column(ForeignKey("act_sections.id"))
    expected_raw_text: Mapped[str] = mapped_column(String(1000), nullable=False)
    expected_relationship_type: Mapped[str] = mapped_column(
        String(50), default=RelationshipType.UNKNOWN.value, nullable=False
    )
    expected_target_act_title: Mapped[str | None] = mapped_column(String(500))
    expected_target_section_number: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)

    act = relationship("LegalAct")
    source_section = relationship("ActSection")


class EvaluationRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_runs"

    run_name: Mapped[str] = mapped_column(String(255), nullable=False)
    act_id: Mapped[str | None] = mapped_column(ForeignKey("legal_acts.id"), index=True)
    precision: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    recall: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    f1_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    section_segmentation_accuracy: Mapped[float | None] = mapped_column(Float)
    total_gold_references: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    true_positives: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    false_positives: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    false_negatives: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    run_summary_json: Mapped[dict | None] = mapped_column(JSON)

    act = relationship("LegalAct")
