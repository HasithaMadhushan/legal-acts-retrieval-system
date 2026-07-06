from sqlalchemy import String, cast, or_, text
from sqlalchemy.orm import Session

from app.core.config import LEGAL_DISCLAIMER
from app.core.roles import ProcessingStatus, RelationshipType, UserRole, VerificationStatus
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.models.legal_reference import LegalReference
from app.schemas.search import SearchResponse, SearchResult
from app.services.reference_normalizer import normalize_relationship_type
from app.services.text_cleaner import normalize_for_search

MAX_QUERY_LENGTH = 200
MAX_LIMIT = 100


def search(
    db: Session,
    *,
    query: str,
    role: UserRole,
    year: int | None = None,
    act_number: str | None = None,
    category: str | None = None,
    processing_status: ProcessingStatus | None = None,
    relationship_type: RelationshipType | None = None,
    verification_status: VerificationStatus | None = None,
    mapped_status: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> SearchResponse:
    query = (query or "").strip()
    if len(query) > MAX_QUERY_LENGTH:
        raise ValueError(f"Search query must be {MAX_QUERY_LENGTH} characters or fewer.")
    limit = min(max(limit, 1), MAX_LIMIT)
    offset = max(offset, 0)

    normalized_query = normalize_for_search(query)
    filters = _SearchFilters(
        query=query,
        normalized_query=normalized_query,
        year=year,
        act_number=str(act_number).strip() if act_number else None,
        category=category.strip() if category else None,
        processing_status=processing_status,
        relationship_type=relationship_type,
        verification_status=verification_status,
        mapped_status=mapped_status,
    )

    results: list[SearchResult] = []
    if not (relationship_type or mapped_status):
        results.extend(_act_results(db, filters, role))
        results.extend(_section_results(db, filters, role))
    results.extend(_reference_results(db, filters, role))

    results.sort(key=lambda item: (-item.score, item.result_type, item.title, item.id))
    paged_results = results[offset : offset + limit]

    return SearchResponse(
        query=query,
        results=paged_results,
        total_results=len(results),
        act_results=sum(1 for result in results if result.result_type == "ACT"),
        section_results=sum(1 for result in results if result.result_type == "SECTION"),
        reference_results=sum(1 for result in results if result.result_type == "REFERENCE"),
        limit=limit,
        offset=offset,
        disclaimer=LEGAL_DISCLAIMER,
    )


class _SearchFilters:
    def __init__(
        self,
        *,
        query: str,
        normalized_query: str,
        year: int | None,
        act_number: str | None,
        category: str | None,
        processing_status: ProcessingStatus | None,
        relationship_type: RelationshipType | None,
        verification_status: VerificationStatus | None,
        mapped_status: str | None,
    ) -> None:
        self.query = query
        self.normalized_query = normalized_query
        self.raw_like = f"%{query}%"
        self.like = f"%{normalized_query}%"
        self.year = year
        self.act_number = act_number
        self.category = category
        self.processing_status = processing_status
        self.relationship_type = relationship_type
        self.verification_status = verification_status
        self.mapped_status = mapped_status
        self.query_relationship = normalize_relationship_type(normalized_query)

    @property
    def has_query(self) -> bool:
        return bool(self.normalized_query)


def _act_results(db: Session, filters: _SearchFilters, role: UserRole) -> list[SearchResult]:
    query = _apply_act_filters(db.query(LegalAct), filters, role)
    if filters.has_query:
        conditions = [
            LegalAct.normalized_title.ilike(filters.like),
            LegalAct.act_number.ilike(filters.raw_like),
            cast(LegalAct.year, String).ilike(filters.raw_like),
            LegalAct.category.ilike(filters.raw_like),
            LegalAct.source_name.ilike(filters.raw_like),
            LegalAct.source_file_name.ilike(filters.raw_like),
        ]
        # `raw_text` can be hundreds of KB per Act; an unindexed ILIKE scan over
        # it doesn't hold up in production. On Postgres, match it via the
        # GIN-indexed `search_vector` column instead (see the F-013 migration);
        # SQLite (tests/local dev) keeps the original ILIKE behavior.
        if _is_postgres(db):
            conditions.append(_fulltext_condition("legal_acts", filters.query))
        else:
            conditions.append(LegalAct.raw_text.ilike(filters.raw_like))
        query = query.filter(or_(*conditions))
    results: list[SearchResult] = []
    for act in query.limit(250):
        results.append(
            SearchResult(
                result_type="ACT",
                id=act.id,
                act_id=act.id,
                title=act.title,
                act_number=act.act_number,
                year=act.year,
                category=act.category,
                processing_status=act.processing_status,
                snippet=_snippet(
                    " ".join(
                        item
                        for item in [
                            act.title,
                            act.category or "",
                            act.source_name or "",
                            act.raw_text or "",
                        ]
                        if item
                    ),
                    filters.query,
                ),
                score=_act_score(act, filters, role),
            )
        )
    return results


def _section_results(db: Session, filters: _SearchFilters, role: UserRole) -> list[SearchResult]:
    query = _apply_section_visibility(db.query(ActSection).join(LegalAct), role)
    query = _apply_joined_act_filters(query, filters, role)
    if filters.verification_status and role != UserRole.GENERAL_USER:
        query = query.filter(ActSection.verification_status == filters.verification_status)
    if filters.has_query:
        conditions = [
            ActSection.section_number == filters.query,
            ActSection.section_path.ilike(filters.raw_like),
            ActSection.heading.ilike(filters.raw_like),
            LegalAct.normalized_title.ilike(filters.like),
        ]
        if _is_postgres(db):
            conditions.append(_fulltext_condition("act_sections", filters.query))
        else:
            conditions.append(ActSection.normalized_text.ilike(filters.like))
        query = query.filter(or_(*conditions))
    results: list[SearchResult] = []
    for section in query.limit(500):
        results.append(
            SearchResult(
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
                snippet=_snippet(section.text, filters.query),
                verification_status=section.verification_status,
                score=_section_score(section, filters, role),
            )
        )
    return results


def _reference_results(db: Session, filters: _SearchFilters, role: UserRole) -> list[SearchResult]:
    query = _apply_reference_visibility(
        db.query(LegalReference).join(LegalAct, LegalReference.source_act_id == LegalAct.id),
        role,
    )
    query = _apply_joined_act_filters(query, filters, role)
    if filters.relationship_type:
        query = query.filter(LegalReference.relationship_type == filters.relationship_type)
    if filters.verification_status and role != UserRole.GENERAL_USER:
        query = query.filter(LegalReference.verification_status == filters.verification_status)
    if filters.mapped_status == "mapped":
        query = query.filter(
            or_(
                LegalReference.target_act_id.is_not(None),
                LegalReference.target_section_id.is_not(None),
            )
        )
    elif filters.mapped_status == "unresolved":
        query = query.filter(
            LegalReference.target_act_id.is_(None),
            LegalReference.target_section_id.is_(None),
        )
    if filters.has_query:
        conditions = [
            LegalReference.raw_reference_text.ilike(filters.raw_like),
            LegalReference.context_snippet.ilike(filters.raw_like),
            LegalReference.target_act_title_raw.ilike(filters.raw_like),
            LegalReference.target_act_number.ilike(filters.raw_like),
            cast(LegalReference.target_act_year, String).ilike(filters.raw_like),
            LegalReference.target_section_number.ilike(filters.raw_like),
            LegalReference.target_section_path.ilike(filters.raw_like),
        ]
        if filters.query_relationship:
            conditions.append(LegalReference.relationship_type == filters.query_relationship)
        query = query.filter(or_(*conditions))
    results: list[SearchResult] = []
    for reference in query.limit(500):
        target_section = reference.target_section_number or reference.target_section_path
        results.append(
            SearchResult(
                result_type="REFERENCE",
                id=reference.id,
                act_id=reference.source_act_id,
                section_id=reference.source_section_id,
                reference_id=reference.id,
                title=reference.source_act.title,
                act_number=reference.source_act.act_number,
                year=reference.source_act.year,
                category=reference.source_act.category,
                processing_status=reference.source_act.processing_status,
                section_number=(
                    reference.source_section.section_number if reference.source_section else None
                ),
                section_heading=(
                    reference.source_section.heading if reference.source_section else None
                ),
                snippet=_snippet(reference.context_snippet, filters.query),
                relationship_type=reference.relationship_type,
                verification_status=reference.verification_status,
                target_act_title=_target_act_title(reference),
                target_section=target_section,
                mapped=bool(reference.target_act_id or reference.target_section_id),
                confidence_score=reference.confidence_score,
                score=_reference_score(reference, filters, role),
            )
        )
    return results


def _is_postgres(db: Session) -> bool:
    return db.get_bind().dialect.name == "postgresql"


def _fulltext_condition(table: str, query: str):
    """A Postgres full-text match against `{table}.search_vector` (F-013).

    `search_vector` is a generated, GIN-indexed tsvector column added by the
    `20260706_01_postgres_fulltext_search` migration -- Postgres-only, so
    callers must guard this with `_is_postgres(db)` first.
    """
    return text(f"{table}.search_vector @@ plainto_tsquery('english', :fts_query)").bindparams(
        fts_query=query
    )


def _apply_act_filters(query, filters: _SearchFilters, role: UserRole):
    query = _apply_act_visibility(query, role)
    if filters.year:
        query = query.filter(LegalAct.year == filters.year)
    if filters.act_number:
        query = query.filter(LegalAct.act_number == filters.act_number)
    if filters.category:
        query = query.filter(LegalAct.category.ilike(f"%{filters.category}%"))
    if filters.processing_status:
        query = query.filter(LegalAct.processing_status == filters.processing_status)
    return query


def _apply_joined_act_filters(query, filters: _SearchFilters, role: UserRole):
    query = _apply_joined_act_visibility(query, role)
    if filters.year:
        query = query.filter(LegalAct.year == filters.year)
    if filters.act_number:
        query = query.filter(LegalAct.act_number == filters.act_number)
    if filters.category:
        query = query.filter(LegalAct.category.ilike(f"%{filters.category}%"))
    if filters.processing_status:
        query = query.filter(LegalAct.processing_status == filters.processing_status)
    return query


def _apply_act_visibility(query, role: UserRole):
    if role == UserRole.ADMIN:
        return query
    return query.filter(
        LegalAct.processing_status.in_([ProcessingStatus.PROCESSED, ProcessingStatus.VERIFIED])
    )


def _apply_joined_act_visibility(query, role: UserRole):
    if role == UserRole.ADMIN:
        return query
    return query.filter(
        LegalAct.processing_status.in_([ProcessingStatus.PROCESSED, ProcessingStatus.VERIFIED])
    )


def _apply_section_visibility(query, role: UserRole):
    if role == UserRole.GENERAL_USER:
        return query.filter(ActSection.verification_status == VerificationStatus.VERIFIED)
    return query


def _apply_reference_visibility(query, role: UserRole):
    if role == UserRole.GENERAL_USER:
        return query.filter(
            LegalReference.verification_status == VerificationStatus.VERIFIED,
            or_(
                LegalReference.target_act_id.is_not(None),
                LegalReference.target_section_id.is_not(None),
            ),
        )
    return query


def _act_score(act: LegalAct, filters: _SearchFilters, role: UserRole) -> float:
    score = 0.3
    title = normalize_for_search(act.title)
    if filters.normalized_query:
        if filters.normalized_query == title:
            score += 9.0
        elif filters.normalized_query in title:
            score += 5.5
        if filters.act_number and act.act_number == filters.act_number:
            score += 4.5
        elif act.act_number and filters.query == act.act_number:
            score += 4.5
        if act.year and filters.query == str(act.year):
            score += 2.0
        if act.category and filters.normalized_query in normalize_for_search(act.category):
            score += 1.5
        if act.raw_text and filters.query.lower() in act.raw_text.lower():
            score += 0.8
    if act.processing_status == ProcessingStatus.VERIFIED:
        score += 0.3
    elif role != UserRole.ADMIN and act.processing_status == ProcessingStatus.PROCESSED:
        score += 0.15
    return score


def _section_score(section: ActSection, filters: _SearchFilters, role: UserRole) -> float:
    score = 0.25
    heading = normalize_for_search(section.heading)
    if filters.normalized_query:
        if section.section_number == filters.query or section.section_path == filters.query:
            score += 5.5
        if heading and filters.normalized_query == heading:
            score += 5.0
        elif heading and filters.normalized_query in heading:
            score += 3.6
        if filters.normalized_query in section.normalized_text:
            score += 1.6
        if filters.normalized_query in normalize_for_search(section.act.title):
            score += 1.2
    if section.verification_status == VerificationStatus.VERIFIED:
        score += 0.4 if role != UserRole.ADMIN else 0.2
    return score


def _reference_score(reference: LegalReference, filters: _SearchFilters, role: UserRole) -> float:
    score = 0.2 + reference.confidence_score
    if filters.relationship_type and reference.relationship_type == filters.relationship_type:
        score += 2.5
    if filters.query_relationship and reference.relationship_type == filters.query_relationship:
        score += 3.2
    if filters.query:
        lowered_query = filters.query.lower()
        if lowered_query in reference.raw_reference_text.lower():
            score += 2.4
        if lowered_query in reference.context_snippet.lower():
            score += 1.5
        if (
            reference.target_act_title_raw
            and lowered_query in reference.target_act_title_raw.lower()
        ):
            score += 1.8
        if (
            reference.target_section_number
            and lowered_query == reference.target_section_number.lower()
        ):
            score += 2.0
        if reference.target_section_path and lowered_query in reference.target_section_path.lower():
            score += 1.4
    if reference.verification_status == VerificationStatus.VERIFIED:
        score += 0.4 if role != UserRole.ADMIN else 0.2
    if reference.target_act_id or reference.target_section_id:
        score += 0.2
    return score


def _snippet(text: str, query: str, width: int = 220) -> str:
    collapsed = " ".join((text or "").split())
    if not query:
        return collapsed[:width]
    index = collapsed.lower().find(query.lower())
    if index < 0:
        return collapsed[:width]
    start = max(0, index - width // 3)
    return collapsed[start : start + width]


def _target_act_title(reference: LegalReference) -> str | None:
    return reference.target_act.title if reference.target_act else reference.target_act_title_raw
