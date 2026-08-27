import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.roles import ParserName, ProcessingJobStatus, ProcessingStatus


class LegalActRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    normalized_title: str
    act_number: str | None
    year: int | None
    certification_date: date | None
    publication_date: date | None
    category: str | None
    source_name: str | None
    source_url: str | None
    source_file_name: str
    file_size: int | None
    mime_type: str | None
    page_count: int | None
    processing_status: ProcessingStatus
    parser_used: ParserName
    processing_error: str | None
    uploaded_by_user_id: str | None
    uploaded_at: datetime
    updated_at: datetime


class LegalActBrowseRead(LegalActRead):
    verified_section_count: int
    verified_reference_count: int
    last_verified_at: datetime | None


class ExtractionArtifactRead(BaseModel):
    present: bool
    schema_version: str | None = None
    sha256_prefix: str | None = None
    created_at: datetime | None = None
    parser_name: str | None = None
    has_physical_pages: bool | None = None
    integrity_warning: bool = False


class LegalActDetail(LegalActRead):
    raw_text: str | None = None
    extraction_artifact: ExtractionArtifactRead | None = None


class LegalActUpdate(BaseModel):
    title: str | None = None
    act_number: str | None = None
    year: int | None = None
    certification_date: date | None = None
    publication_date: date | None = None
    category: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    processing_status: ProcessingStatus | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str:
        if value is None or not value.strip():
            raise ValueError("Title must not be empty.")
        return value.strip()

    @field_validator("year")
    @classmethod
    def validate_year(cls, value: int | None) -> int | None:
        if value is not None and not 1800 <= value <= 2100:
            raise ValueError("Year must be between 1800 and 2100.")
        return value

    @field_validator("act_number")
    @classmethod
    def validate_act_number(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            return None
        if not re.fullmatch(r"[A-Za-z0-9 ._/-]{1,50}", cleaned):
            raise ValueError("Act number contains unsupported characters.")
        return cleaned

    @field_validator("category", "source_name", "source_url")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        return cleaned or None


class ProcessingJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    act_id: str
    status: ProcessingJobStatus
    current_step: str
    progress_percent: int
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    summary_json: dict | None
    created_by_user_id: str | None
    created_at: datetime
    updated_at: datetime


class VerificationSummaryRead(BaseModel):
    act_id: str
    total_sections: int
    pending_sections: int
    needs_review_sections: int
    verified_sections: int
    rejected_sections: int
    total_references: int
    pending_references: int
    needs_review_references: int
    verified_references: int
    rejected_references: int
    mapped_references: int
    unresolved_references: int
