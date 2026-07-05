from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.roles import ProcessingStatus, RelationshipType, SavedItemType, VerificationStatus


class SavedItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    item_type: SavedItemType
    act_id: str | None
    section_id: str | None
    reference_id: str | None
    note: str | None
    item_title: str | None = None
    act_title: str | None = None
    act_number: str | None = None
    year: int | None = None
    section_number: str | None = None
    section_heading: str | None = None
    relationship_type: RelationshipType | None = None
    raw_reference_text: str | None = None
    context_snippet: str | None = None
    verification_status: VerificationStatus | None = None
    processing_status: ProcessingStatus | None = None
    mapped: bool | None = None
    target_act_title: str | None = None
    target_act_number: str | None = None
    target_act_year: int | None = None
    target_section_number: str | None = None
    target_section_path: str | None = None
    mapped_target_act_id: str | None = None
    mapped_target_section_id: str | None = None
    created_at: datetime
    updated_at: datetime


class SavedItemListResponse(BaseModel):
    items: list[SavedItemRead]
    total_results: int
    limit: int
    offset: int
    counts_by_type: dict[str, int]


class SavedItemCreate(BaseModel):
    item_type: SavedItemType
    act_id: str | None = None
    section_id: str | None = None
    reference_id: str | None = None
    note: str | None = None

    @field_validator("note")
    @classmethod
    def trim_note(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        return cleaned or None


class SavedItemUpdate(BaseModel):
    note: str | None = None

    @field_validator("note")
    @classmethod
    def trim_note(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        return cleaned or None
