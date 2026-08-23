from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.roles import ReadingHistoryItemType
from app.db.base import Base
from app.models.mixins import UUIDPrimaryKeyMixin


class ReadingHistoryItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "reading_history_items"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    item_type: Mapped[ReadingHistoryItemType] = mapped_column(
        Enum(ReadingHistoryItemType, name="reading_history_item_type"),
        nullable=False,
    )
    act_id: Mapped[str] = mapped_column(ForeignKey("legal_acts.id"), index=True, nullable=False)
    section_id: Mapped[str | None] = mapped_column(ForeignKey("act_sections.id"), index=True)
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="reading_history_items")
    act = relationship("LegalAct")
    section = relationship("ActSection")
