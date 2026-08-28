from pydantic import BaseModel

from app.core.roles import ProcessingStatus, RelationshipType, VerificationStatus

SEMANTIC_SEARCH_DISABLED = "Semantic search is not enabled. Use Keyword or All methods."
SEMANTIC_SEARCH_NOT_READY = "Semantic search is enabled but not ready. Use Keyword or All methods."


class SearchResult(BaseModel):
    result_type: str
    id: str
    act_id: str | None = None
    section_id: str | None = None
    reference_id: str | None = None
    title: str
    act_number: str | None = None
    year: int | None = None
    category: str | None = None
    processing_status: ProcessingStatus | None = None
    section_number: str | None = None
    section_heading: str | None = None
    section_path: str | None = None
    snippet: str
    relationship_type: RelationshipType | None = None
    verification_status: VerificationStatus | None = None
    target_act_title: str | None = None
    target_section: str | None = None
    mapped: bool | None = None
    confidence_score: float | None = None
    score: float
    score_components: dict[str, float | int | None] | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total_results: int
    act_results: int
    section_results: int
    reference_results: int
    limit: int
    offset: int
    disclaimer: str


class SuggestResponse(BaseModel):
    suggestions: list[str]
