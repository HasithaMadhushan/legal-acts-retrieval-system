from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.roles import SectionType, VerificationStatus


class SectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    act_id: str
    section_number: str
    section_path: str | None
    heading: str | None
    section_type: SectionType
    text: str
    normalized_text: str
    page_start: int | None
    page_end: int | None
    sort_order: int
    parent_section_id: str | None
    verification_status: VerificationStatus
    created_at: datetime
    updated_at: datetime


class SectionUpdate(BaseModel):
    section_number: str | None = None
    section_path: str | None = None
    heading: str | None = None
    section_type: SectionType | None = None
    text: str | None = None
    verification_status: VerificationStatus | None = None

    @field_validator("section_number", "text")
    @classmethod
    def required_text_fields(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Section number and text must not be empty.")
        return cleaned

    @field_validator("section_path", "heading")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        return cleaned or None
