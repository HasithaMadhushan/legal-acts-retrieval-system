from typing import Literal

from pydantic import BaseModel

from app.core.roles import RelationshipType, VerificationStatus

RelationshipDirection = Literal["outgoing", "incoming"]


class RelationshipRow(BaseModel):
    id: str
    source_act_id: str
    source_act_title: str | None
    source_section_id: str | None
    source_section_number: str | None
    source_section_heading: str | None
    relationship_type: RelationshipType
    target_act_id: str | None
    target_act_title: str | None
    target_section_id: str | None
    target_section_number: str | None
    target_section_heading: str | None
    target_act_title_raw: str | None
    target_act_number: str | None
    target_act_year: int | None
    target_section_path: str | None
    direction: RelationshipDirection
    mapped: bool
    verification_status: VerificationStatus
    confidence_score: float
    raw_reference_text: str
    context_snippet: str


class RelationshipSummary(BaseModel):
    total_results: int
    outgoing_count: int
    incoming_count: int
    mapped_count: int
    unresolved_count: int
    by_relationship_type: dict[str, int]
    by_verification_status: dict[str, int]


class RelationshipListResponse(BaseModel):
    scope_type: Literal["act", "section"]
    scope_id: str
    relationships: list[RelationshipRow]
    summary: RelationshipSummary
    limit: int
    offset: int
    total_results: int
    disclaimer: str


class RelationshipGraphNode(BaseModel):
    id: str
    label: str
    type: str


class RelationshipGraphEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str
    status: str


class RelationshipGraphResponse(BaseModel):
    depth: int
    nodes: list[RelationshipGraphNode]
    edges: list[RelationshipGraphEdge]
    summary: RelationshipSummary
    disclaimer: str
