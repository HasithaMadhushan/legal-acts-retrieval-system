from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.roles import SavedItemType
from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class SavedItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "saved_items"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    item_type: Mapped[SavedItemType] = mapped_column(
        Enum(SavedItemType, name="saved_item_type"), nullable=False
    )
    act_id: Mapped[str | None] = mapped_column(ForeignKey("legal_acts.id"))
    section_id: Mapped[str | None] = mapped_column(ForeignKey("act_sections.id"))
    reference_id: Mapped[str | None] = mapped_column(ForeignKey("legal_references.id"))
    note: Mapped[str | None] = mapped_column(Text)

    user = relationship("User", back_populates="saved_items")
    act = relationship("LegalAct")
    section = relationship("ActSection")
    reference = relationship("LegalReference")
