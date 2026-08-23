from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.roles import ReadingHistoryItemType


class ReadingHistoryCreate(BaseModel):
    item_type: ReadingHistoryItemType
    act_id: str
    section_id: str | None = None


class ReadingHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    item_type: ReadingHistoryItemType
    act_id: str
    section_id: str | None
    viewed_at: datetime
    act_title: str
    act_number: str | None
    act_year: int | None
    section_number: str | None
    section_heading: str | None
    href: str


class ReadingHistoryListResponse(BaseModel):
    items: list[ReadingHistoryRead]
    total_results: int
