from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class LlmExtractionCache(TimestampMixin, Base):
    __tablename__ = "llm_extraction_cache"

    content_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    response_json: Mapped[dict] = mapped_column(JSON, nullable=False)
