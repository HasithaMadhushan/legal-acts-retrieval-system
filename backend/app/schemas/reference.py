from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.roles import ExtractionMethod, RelationshipType, VerificationStatus


class ReferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_act_id: str
    source_section_id: str | None
    raw_reference_text: str
    context_snippet: str
    relationship_type: RelationshipType
    target_act_title_raw: str | None
    target_act_number: str | None
    target_act_year: int | None
    target_section_number: str | None
    target_section_path: str | None
    target_act_id: str | None
    target_section_id: str | None
    confidence_score: float
    extraction_method: ExtractionMethod
    verification_status: VerificationStatus
    verified_by_user_id: str | None
    verified_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ReferenceUpdate(BaseModel):
    raw_reference_text: str | None = None
    context_snippet: str | None = None
    relationship_type: RelationshipType | None = None
    target_act_title_raw: str | None = None
    target_act_number: str | None = None
    target_act_year: int | None = None
    target_section_number: str | None = None
    target_section_path: str | None = None
    target_act_id: str | None = None
    target_section_id: str | None = None
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    verification_status: VerificationStatus | None = None
    notes: str | None = None

    @field_validator("raw_reference_text", "context_snippet")
    @classmethod
    def trim_required_update_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Raw reference and context text must not be blank.")
        return cleaned

    @field_validator(
        "target_act_title_raw",
        "target_act_number",
        "target_section_number",
        "target_section_path",
        "notes",
    )
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        return cleaned or None


class ReferenceCreate(BaseModel):
    source_act_id: str
    source_section_id: str | None = None
    raw_reference_text: str = Field(min_length=1, max_length=1000)
    context_snippet: str = Field(min_length=1)
    relationship_type: RelationshipType
    target_act_title_raw: str | None = None
    target_act_number: str | None = None
    target_act_year: int | None = None
    target_section_number: str | None = None
    target_section_path: str | None = None
    target_act_id: str | None = None
    target_section_id: str | None = None
    confidence_score: float = Field(default=0.5, ge=0, le=1)
    verification_status: VerificationStatus = VerificationStatus.NEEDS_REVIEW
    notes: str | None = None

    @field_validator(
        "raw_reference_text",
        "context_snippet",
        "target_act_title_raw",
        "target_act_number",
        "target_section_number",
        "target_section_path",
        "notes",
    )
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Text fields must not be blank when provided.")
        return cleaned


class LinkTargetRequest(BaseModel):
    target_act_id: str | None = None
    target_section_id: str | None = None
    notes: str | None = None
