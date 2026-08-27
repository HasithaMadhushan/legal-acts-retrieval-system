from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import LEGAL_DISCLAIMER
from app.core.roles import RelationshipType, UserRole, VerificationStatus
from app.db.session import get_db
from app.models.legal_reference import LegalReference
from app.models.user import User
from app.schemas.relationship import (
    RelationshipGraphEdge,
    RelationshipGraphNode,
    RelationshipGraphResponse,
    RelationshipListResponse,
    RelationshipRow,
    RelationshipSummary,
)

router = APIRouter(prefix="/relationships", tags=["relationships"])

DirectionFilter = Literal["outgoing", "incoming", "all"]
MappedFilter = Literal["mapped", "unresolved"]
ScopeType = Literal["act", "section"]
VerificationStatusFilter = Literal[
    "PENDING",
    "VERIFIED",
    "REJECTED",
    "NEEDS_REVIEW",
    "verified_pending",
]


@router.get("/act/{act_id}", response_model=RelationshipListResponse)
def act_relationships(
    act_id: str,
    relationship_type: RelationshipType | None = None,
    verification_status: VerificationStatusFilter | None = None,
    mapped_status: MappedFilter | None = None,
    direction: DirectionFilter = "all",
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RelationshipListResponse:
    references = _relationships_for_scope(
        db,
        current_user,
        scope_type="act",
        scope_id=act_id,
        direction=direction,
        relationship_type=relationship_type,
        verification_status=verification_status,
        mapped_status=mapped_status,
    )
    return _list_response("act", act_id, references, limit, offset)


@router.get("/section/{section_id}", response_model=RelationshipListResponse)
def section_relationships(
    section_id: str,
    relationship_type: RelationshipType | None = None,
    verification_status: VerificationStatusFilter | None = None,
    mapped_status: MappedFilter | None = None,
    direction: DirectionFilter = "all",
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RelationshipListResponse:
    references = _relationships_for_scope(
        db,
        current_user,
        scope_type="section",
        scope_id=section_id,
        direction=direction,
        relationship_type=relationship_type,
        verification_status=verification_status,
        mapped_status=mapped_status,
    )
    return _list_response("section", section_id, references, limit, offset)


@router.get("/graph", response_model=RelationshipGraphResponse)
def relationship_graph(
    act_id: str | None = None,
    section_id: str | None = None,
    relationship_type: RelationshipType | None = None,
    verification_status: VerificationStatusFilter | None = None,
    mapped_status: MappedFilter | None = None,
    direction: DirectionFilter = "all",
    depth: int = Query(default=1, ge=1, le=2),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RelationshipGraphResponse:
    if section_id:
        scope_type: ScopeType = "section"
        scope_id = section_id
    else:
        scope_type = "act"
        scope_id = act_id or ""
    references = _relationships_for_scope(
        db,
        current_user,
        scope_type=scope_type,
        scope_id=scope_id,
        direction=direction,
        relationship_type=relationship_type,
        verification_status=verification_status,
        mapped_status=mapped_status,
    )
    references = [
        reference
        for reference in references
        if reference.target_act_id is None
        or reference.source_act_id != reference.target_act_id
    ]
    nodes: dict[str, RelationshipGraphNode] = {}
    edges: list[RelationshipGraphEdge] = []
    for reference in references:
        source_act = reference.source_act
        target_act = reference.target_act
        if not source_act or not target_act:
            continue
        nodes[source_act.id] = RelationshipGraphNode(
            id=source_act.id, label=source_act.title, type="ACT"
        )
        nodes[target_act.id] = RelationshipGraphNode(
            id=target_act.id, label=target_act.title, type="ACT"
        )
        edges.append(
            RelationshipGraphEdge(
                id=reference.id,
                source=source_act.id,
                target=target_act.id,
                label=reference.relationship_type.value,
                status=reference.verification_status.value,
            )
        )
    return RelationshipGraphResponse(
        depth=depth,
        nodes=list(nodes.values()),
        edges=edges,
        summary=_summary(_rows(scope_type, scope_id, references)),
        disclaimer=LEGAL_DISCLAIMER,
    )


def _relationships_for_scope(
    db: Session,
    current_user: User,
    *,
    scope_type: ScopeType,
    scope_id: str,
    direction: DirectionFilter,
    relationship_type: RelationshipType | None,
    verification_status: VerificationStatusFilter | None,
    mapped_status: MappedFilter | None,
) -> list[LegalReference]:
    query = _visible_reference_query(db, current_user)
    if scope_id:
        if scope_type == "act":
            outgoing_filter = LegalReference.source_act_id == scope_id
            incoming_filter = LegalReference.target_act_id == scope_id
        else:
            outgoing_filter = LegalReference.source_section_id == scope_id
            incoming_filter = LegalReference.target_section_id == scope_id
        if direction == "outgoing":
            query = query.filter(outgoing_filter)
        elif direction == "incoming":
            query = query.filter(incoming_filter)
        else:
            query = query.filter(or_(outgoing_filter, incoming_filter))

    if relationship_type:
        query = query.filter(LegalReference.relationship_type == relationship_type)
    query = _filter_verification_status(query, verification_status)
    if mapped_status == "mapped":
        query = query.filter(
            or_(
                LegalReference.target_act_id.is_not(None),
                LegalReference.target_section_id.is_not(None),
            )
        )
    elif mapped_status == "unresolved":
        query = query.filter(
            LegalReference.target_act_id.is_(None),
            LegalReference.target_section_id.is_(None),
        )
    return query.order_by(LegalReference.created_at.desc()).all()


def _filter_verification_status(query, verification_status: VerificationStatusFilter | None):
    if not verification_status:
        return query
    if verification_status == "verified_pending":
        return query.filter(
            LegalReference.verification_status.in_(
                (
                    VerificationStatus.VERIFIED,
                    VerificationStatus.PENDING,
                    VerificationStatus.NEEDS_REVIEW,
                )
            )
        )
    return query.filter(
        LegalReference.verification_status == VerificationStatus(verification_status)
    )


def _visible_reference_query(db: Session, current_user: User):
    query = db.query(LegalReference)
    if current_user.role == UserRole.GENERAL_USER:
        return query.filter(
            LegalReference.verification_status == VerificationStatus.VERIFIED,
            or_(
                LegalReference.target_act_id.is_not(None),
                LegalReference.target_section_id.is_not(None),
            ),
        )
    return query


def _list_response(
    scope_type: ScopeType,
    scope_id: str,
    references: list[LegalReference],
    limit: int,
    offset: int,
) -> RelationshipListResponse:
    rows = _rows(scope_type, scope_id, references)
    paged = rows[offset : offset + limit]
    return RelationshipListResponse(
        scope_type=scope_type,
        scope_id=scope_id,
        relationships=paged,
        summary=_summary(rows),
        limit=limit,
        offset=offset,
        total_results=len(rows),
        disclaimer=LEGAL_DISCLAIMER,
    )


def _rows(
    scope_type: ScopeType, scope_id: str, references: list[LegalReference]
) -> list[RelationshipRow]:
    return [_reference_row(scope_type, scope_id, reference) for reference in references]


def _summary(rows: list[RelationshipRow]) -> RelationshipSummary:
    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for row in rows:
        relationship_value = row.relationship_type.value
        status_value = row.verification_status.value
        by_type[relationship_value] = by_type.get(relationship_value, 0) + 1
        by_status[status_value] = by_status.get(status_value, 0) + 1
    return RelationshipSummary(
        total_results=len(rows),
        outgoing_count=sum(1 for row in rows if row.direction == "outgoing"),
        incoming_count=sum(1 for row in rows if row.direction == "incoming"),
        mapped_count=sum(1 for row in rows if row.mapped),
        unresolved_count=sum(1 for row in rows if not row.mapped),
        by_relationship_type=by_type,
        by_verification_status=by_status,
    )


def _reference_row(
    scope_type: ScopeType, scope_id: str, reference: LegalReference
) -> RelationshipRow:
    direction = _direction(scope_type, scope_id, reference)
    source_section = reference.source_section
    target_section = reference.target_section
    target_act = reference.target_act
    return RelationshipRow(
        id=reference.id,
        source_act_id=reference.source_act_id,
        source_act_title=reference.source_act.title if reference.source_act else None,
        source_section_id=reference.source_section_id,
        source_section_number=source_section.section_number if source_section else None,
        source_section_heading=source_section.heading if source_section else None,
        relationship_type=reference.relationship_type,
        target_act_id=reference.target_act_id,
        target_act_title=target_act.title if target_act else None,
        target_section_id=reference.target_section_id,
        target_section_number=(
            target_section.section_number
            if target_section
            else reference.target_section_number
        ),
        target_section_heading=target_section.heading if target_section else None,
        target_act_title_raw=reference.target_act_title_raw,
        target_act_number=reference.target_act_number,
        target_act_year=reference.target_act_year,
        target_section_path=reference.target_section_path,
        direction=direction,
        mapped=bool(reference.target_act_id or reference.target_section_id),
        verification_status=reference.verification_status,
        confidence_score=reference.confidence_score,
        raw_reference_text=reference.raw_reference_text,
        context_snippet=reference.context_snippet,
    )


def _direction(
    scope_type: ScopeType, scope_id: str, reference: LegalReference
) -> Literal["outgoing", "incoming"]:
    if scope_type == "act" and reference.source_act_id == scope_id:
        return "outgoing"
    if scope_type == "section" and reference.source_section_id == scope_id:
        return "outgoing"
    return "incoming"
