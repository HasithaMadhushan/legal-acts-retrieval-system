"""Nearest-neighbour section search for semantic mode.

PostgreSQL ranks with pgvector cosine distance (``<=>``) so the HNSW index can
serve ordered, paginated candidates. Score is a clamped transform of that
distance:

    score = round(max(1.0 - cosine_distance, 0.0) * 100, 2)

For L2-normalized embeddings this matches cosine similarity scaled to 0–100.
``total_results`` / ``section_results`` are the exact count of visible READY
sections whose stored embedding identity matches the configured provider.

SQLite cannot execute pgvector operators. A Python scoring loop remains only as
a **non-production** unit-test fallback and must not be used on PostgreSQL.
"""

from __future__ import annotations

import math

from pgvector.sqlalchemy import Vector
from sqlalchemy import and_, or_, type_coerce
from sqlalchemy.orm import Query, Session

from app.core.config import LEGAL_DISCLAIMER
from app.core.roles import EmbeddingStatus, UserRole
from app.db.types import SECTION_EMBEDDING_DIMENSION
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.schemas.search import SearchResponse, SearchResult
from app.services.embedding_providers import get_embedding_provider
from app.services.embedding_service import EmbeddingService
from app.services.search_intent import SearchIntent, exact_identifier_boost
from app.services.search_service import (
    _apply_joined_act_filters,
    _apply_section_visibility,
    _snippet,
)

_SCORE_SCALE = 100.0


def score_from_cosine_distance(distance: float) -> float:
    """Map cosine distance to the documented 0–100 search score."""
    return round(max(1.0 - float(distance), 0.0) * _SCORE_SCALE, 2)


def cosine_distance_expression(query_vector: list[float]):
    """HNSW-friendly cosine distance; type_coerce avoids a CAST that would hide the index."""
    return type_coerce(ActSection.embedding, Vector(SECTION_EMBEDDING_DIMENSION)).cosine_distance(
        query_vector
    )


def postgres_nearest_neighbour_query(
    section_query: Query, query_vector: list[float], *, limit: int, offset: int
) -> Query:
    distance = cosine_distance_expression(query_vector)
    return (
        section_query.add_columns(distance.label("distance"))
        .order_by(distance.asc())
        .limit(limit)
        .offset(offset)
    )


def search_semantic_sections(
    db: Session,
    filters,
    role: UserRole,
    *,
    limit: int,
    offset: int,
) -> SearchResponse:
    query_vector = EmbeddingService().embed_query(filters.query)
    candidates = _visible_ready_sections(db, filters, role)
    if _is_postgres(db):
        return _postgres_results(candidates, query_vector, filters, limit, offset)
    return _sqlite_fallback_results(candidates, query_vector, filters, limit, offset)


def _visible_ready_sections(db: Session, filters, role: UserRole) -> Query:
    query = _apply_section_visibility(db.query(ActSection).join(LegalAct), role)
    query = _apply_joined_act_filters(query, filters, role)
    if filters.verification_status and role != UserRole.GENERAL_USER:
        query = query.filter(ActSection.verification_status == filters.verification_status)
    return _filter_ready_current_identity(query)


def _filter_ready_current_identity(query: Query) -> Query:
    provider = get_embedding_provider()
    return (
        query.filter(ActSection.embedding.is_not(None))
        .filter(ActSection.embedding_status == EmbeddingStatus.READY)
        .filter(ActSection.embedding_provider == provider.provider_name)
        .filter(ActSection.embedding_model == provider.model_name)
        .filter(ActSection.embedding_dimension == provider.dimension)
    )


def _postgres_results(
    candidates: Query,
    query_vector: list[float],
    filters,
    limit: int,
    offset: int,
) -> SearchResponse:
    total = candidates.count()
    exact_predicate = _exact_section_predicate(filters.intent)
    if exact_predicate is None:
        rows = postgres_nearest_neighbour_query(
            candidates, query_vector, limit=limit, offset=offset
        ).all()
    else:
        exact_candidates = candidates.filter(exact_predicate)
        exact_total = exact_candidates.count()
        exact_limit = min(limit, max(exact_total - offset, 0))
        rows = []
        if exact_limit:
            rows.extend(
                postgres_nearest_neighbour_query(
                    exact_candidates,
                    query_vector,
                    limit=exact_limit,
                    offset=offset,
                ).all()
            )
        semantic_limit = limit - len(rows)
        if semantic_limit:
            semantic_offset = max(offset - exact_total, 0)
            rows.extend(
                postgres_nearest_neighbour_query(
                    candidates.filter(exact_predicate.is_not(True)),
                    query_vector,
                    limit=semantic_limit,
                    offset=semantic_offset,
                ).all()
            )
    results = [
        _section_result(
            section,
            filters,
            score_from_cosine_distance(float(distance))
            + _section_identifier_boost(section, filters.intent),
        )
        for section, distance in rows
    ]
    return _response(filters.query, results, total, limit, offset)


def _sqlite_fallback_results(
    candidates: Query,
    query_vector: list[float],
    filters,
    limit: int,
    offset: int,
) -> SearchResponse:
    """Non-production SQLite fallback: JSON embeddings cannot use pgvector ``<=>``."""
    scored: list[tuple[float, float, str, SearchResult]] = []
    for section in candidates.all():
        distance = _python_cosine_distance(query_vector, section.embedding)
        boost = _section_identifier_boost(section, filters.intent)
        scored.append(
            (
                -boost,
                distance,
                section.id,
                _section_result(
                    section,
                    filters,
                    score_from_cosine_distance(distance) + boost,
                ),
            )
        )
    scored.sort(key=lambda item: (item[0], item[1], item[2]))
    total = len(scored)
    paged = [item[3] for item in scored[offset : offset + limit]]
    return _response(filters.query, paged, total, limit, offset)


def _exact_section_predicate(intent: SearchIntent):
    act_predicate = None
    if intent.has_act_identifier:
        act_predicate = and_(
            LegalAct.act_number == intent.act_number,
            LegalAct.year == intent.act_year,
        )
    elif intent.act_title:
        act_predicate = LegalAct.normalized_title == intent.act_title

    section_predicate = None
    if intent.section_path and intent.section_path != intent.section_number:
        section_predicate = or_(
            ActSection.section_path == intent.section_path,
            ActSection.section_number == intent.section_path,
        )
    elif intent.section_number:
        section_predicate = or_(
            ActSection.section_number == intent.section_number,
            ActSection.section_path == intent.section_number,
        )

    if act_predicate is not None and section_predicate is not None:
        return and_(act_predicate, section_predicate)
    return section_predicate if section_predicate is not None else act_predicate


def _section_identifier_boost(section: ActSection, intent: SearchIntent) -> float:
    return exact_identifier_boost(
        intent,
        result_type="SECTION",
        act_number=section.act.act_number,
        year=section.act.year,
        title=section.act.title,
        section_number=section.section_number,
        section_path=section.section_path or section.section_number,
    )


def _python_cosine_distance(left: list[float], right: list[float] | None) -> float:
    if not left or not right or len(left) != len(right):
        return 1.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm_left = math.sqrt(sum(a * a for a in left)) or 1.0
    norm_right = math.sqrt(sum(b * b for b in right)) or 1.0
    similarity = max(-1.0, min(1.0, dot / (norm_left * norm_right)))
    return 1.0 - similarity


def _section_result(section: ActSection, filters, score: float) -> SearchResult:
    return SearchResult(
        result_type="SECTION",
        id=section.id,
        act_id=section.act_id,
        section_id=section.id,
        title=section.act.title,
        act_number=section.act.act_number,
        year=section.act.year,
        category=section.act.category,
        processing_status=section.act.processing_status,
        section_number=section.section_number,
        section_heading=section.heading,
        section_path=section.section_path,
        snippet=_snippet(section.text, filters.query),
        verification_status=section.verification_status,
        score=score,
    )


def _response(
    query: str, results: list[SearchResult], total: int, limit: int, offset: int
) -> SearchResponse:
    return SearchResponse(
        query=query,
        results=results,
        total_results=total,
        act_results=0,
        section_results=total,
        reference_results=0,
        limit=limit,
        offset=offset,
        disclaimer=LEGAL_DISCLAIMER,
    )


def _is_postgres(db: Session) -> bool:
    return db.get_bind().dialect.name == "postgresql"
