import difflib
from dataclasses import dataclass, field

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.roles import RelationshipType, SectionType, VerificationStatus
from app.models.act_section import ActSection
from app.models.legal_act import LegalAct
from app.models.legal_reference import LegalReference
from app.services.reference_normalizer import (
    normalize_act_number,
    normalize_act_title,
    normalize_chapter_reference,
    normalize_relationship_type,
    normalize_schedule_reference,
    normalize_section_reference,
    normalize_target_path,
)


@dataclass
class MappingContext:
    source_act: LegalAct
    principal_act: LegalAct | None = None
    principal_source: str | None = None


@dataclass
class MappingResult:
    reference: LegalReference
    mapped_act: bool = False
    mapped_section: bool = False
    used_principal_context: bool = False
    confidence_band: str = "unresolved"
    warnings: list[str] = field(default_factory=list)
    resolved_act: LegalAct | None = None


def build_mapping_context(
    db: Session, source_act: LegalAct, references: list[LegalReference]
) -> MappingContext:
    context = MappingContext(source_act=source_act)
    for reference in references:
        if _is_principal_enactment(reference.target_act_title_raw):
            continue
        result = _find_target_act(db, reference, context=None)
        if result.act:
            context.principal_act = result.act
            context.principal_source = reference.raw_reference_text
            break
    return context


def map_reference(db: Session, reference: LegalReference) -> LegalReference:
    return map_reference_with_result(db, reference).reference


def map_references(
    db: Session, source_act: LegalAct, references: list[LegalReference]
) -> list[MappingResult]:
    """Map every reference extracted from `source_act`, tracking the
    principal-enactment context sequentially in document order.

    Fixes F-005: rather than picking one Act-wide "principal enactment" from
    the first citation found anywhere in the document (wrong for omnibus
    Acts that amend several different Acts in different sections), each bare
    reference ("Section 5 thereof", "the principal enactment") uses the
    closest PRECEDING explicit Act citation instead. `references` must
    already be in document order (see `document_processor.py`, which builds
    it by walking sections in `sort_order`).
    """
    context = MappingContext(source_act=source_act)
    results: list[MappingResult] = []
    for reference in references:
        result = map_reference_with_result(db, reference, context)
        results.append(result)
        if (
            result.resolved_act is not None
            and not result.used_principal_context
            and not _is_principal_enactment(reference.target_act_title_raw)
        ):
            context.principal_act = result.resolved_act
            context.principal_source = reference.raw_reference_text
    return results


def map_reference_with_result(
    db: Session,
    reference: LegalReference,
    context: MappingContext | None = None,
) -> MappingResult:
    _normalize_reference_fields(reference)
    warnings: list[str] = []
    used_principal_context = False

    target_result = _find_target_act(db, reference, context)
    target_act = target_result.act
    used_principal_context = target_result.used_principal_context
    warnings.extend(target_result.warnings)

    target_section = None
    if target_act:
        reference.target_act_id = target_act.id
        target_section = _find_target_section(db, target_act, reference)
        if target_section:
            reference.target_section_id = target_section.id
    else:
        reference.target_act_id = None
        reference.target_section_id = None
        if _has_structured_target(reference):
            warnings.append("Target could not be mapped to an uploaded Act.")
        else:
            warnings.append("Reference has no structured target fields for mapping.")

    confidence_score, confidence_band = _mapping_confidence(
        target_result.match_kind,
        mapped_section=target_section is not None,
        has_structured_target=_has_structured_target(reference),
    )
    reference.confidence_score = confidence_score
    if not target_act or confidence_score < 0.85:
        reference.verification_status = VerificationStatus.NEEDS_REVIEW

    return MappingResult(
        reference=reference,
        mapped_act=target_act is not None,
        mapped_section=target_section is not None,
        used_principal_context=used_principal_context,
        confidence_band=confidence_band,
        warnings=_unique_strings(warnings),
        resolved_act=target_act,
    )


def summarize_mapping(results: list[MappingResult]) -> dict[str, object]:
    warnings: list[str] = []
    for result in results:
        warnings.extend(result.warnings)
    total = len(results)
    mapped_act_count = sum(1 for result in results if result.mapped_act)
    mapped_section_count = sum(1 for result in results if result.mapped_section)
    principal_context_used_count = sum(1 for result in results if result.used_principal_context)
    return {
        "total_references": total,
        "mapped_act_count": mapped_act_count,
        "mapped_section_count": mapped_section_count,
        "unresolved_count": total - mapped_act_count,
        "principal_context_used_count": principal_context_used_count,
        "confidence_bands": {
            "exact": sum(1 for result in results if result.confidence_band == "exact"),
            "partial": sum(1 for result in results if result.confidence_band == "partial"),
            "inferred": sum(1 for result in results if result.confidence_band == "inferred"),
            "unresolved": sum(
                1 for result in results if result.confidence_band == "unresolved"
            ),
        },
        "warnings": _unique_strings(warnings),
    }


@dataclass
class _TargetActResult:
    act: LegalAct | None = None
    match_kind: str = "unresolved"
    used_principal_context: bool = False
    warnings: list[str] = field(default_factory=list)


def _normalize_reference_fields(reference: LegalReference) -> None:
    reference.relationship_type = (
        normalize_relationship_type(reference.relationship_type) or RelationshipType.UNKNOWN
    )
    reference.target_act_number = normalize_act_number(reference.target_act_number)
    reference.target_section_number = normalize_section_reference(reference.target_section_number)
    reference.target_section_path = normalize_target_path(reference.target_section_path)


def _find_target_act(
    db: Session,
    reference: LegalReference,
    context: MappingContext | None,
) -> _TargetActResult:
    if (
        _is_principal_enactment(reference.target_act_title_raw)
        and context
        and context.principal_act
    ):
        return _TargetActResult(
            act=context.principal_act,
            match_kind="inferred",
            used_principal_context=True,
        )

    if _can_use_principal_context(reference, context):
        return _TargetActResult(
            act=context.principal_act,
            match_kind="inferred",
            used_principal_context=True,
            warnings=["Principal enactment context was used for a section or schedule reference."],
        )

    if reference.target_act_number and reference.target_act_year:
        act = (
            db.query(LegalAct)
            .filter(
                LegalAct.act_number == reference.target_act_number,
                LegalAct.year == reference.target_act_year,
            )
            .first()
        )
        if act:
            return _TargetActResult(act=act, match_kind="exact")

    normalized_title = normalize_act_title(reference.target_act_title_raw)
    if normalized_title:
        exact = db.query(LegalAct).filter(LegalAct.normalized_title == normalized_title).first()
        if exact:
            return _TargetActResult(act=exact, match_kind="exact")
        if len(normalized_title) >= 4:
            candidates = (
                db.query(LegalAct)
                .filter(LegalAct.normalized_title.ilike(f"%{normalized_title}%"))
                .all()
            )
            ranked = _rank_partial_title_candidates(normalized_title, candidates)
            if ranked:
                return ranked

    chapter = normalize_chapter_reference(
        reference.target_act_title_raw
    ) or normalize_chapter_reference(reference.target_section_path)
    if chapter:
        normalized_chapter = normalize_act_title(chapter)
        chapter_match = (
            db.query(LegalAct)
            .filter(
                or_(
                    LegalAct.normalized_title.ilike(f"%{normalized_chapter}%"),
                    LegalAct.source_name.ilike(f"%{chapter}%"),
                    LegalAct.source_url.ilike(f"%{chapter}%"),
                )
            )
            .first()
        )
        if chapter_match:
            return _TargetActResult(act=chapter_match, match_kind="partial")

    return _TargetActResult()


# Minimum similarity for a fuzzy title match to be trusted at all, and minimum lead
# a top candidate needs over the runner-up to be trusted as unambiguous (F-004: the
# previous `.first()` on an ILIKE query picked an arbitrary row with no regard for
# match quality or competing candidates).
_PARTIAL_TITLE_MIN_SCORE = 0.5
_PARTIAL_TITLE_MIN_MARGIN = 0.15


def _rank_partial_title_candidates(
    normalized_title: str, candidates: list[LegalAct]
) -> "_TargetActResult | None":
    if not candidates:
        return None
    scored = sorted(
        (
            (
                difflib.SequenceMatcher(None, normalized_title, candidate.normalized_title).ratio(),
                candidate,
            )
            for candidate in candidates
        ),
        key=lambda pair: pair[0],
        reverse=True,
    )
    best_score, best_candidate = scored[0]
    if best_score < _PARTIAL_TITLE_MIN_SCORE:
        return None
    if len(scored) > 1 and (best_score - scored[1][0]) < _PARTIAL_TITLE_MIN_MARGIN:
        return _TargetActResult(
            warnings=[
                "Multiple candidate Acts matched the referenced title with similar "
                "confidence; needs manual review."
            ]
        )
    return _TargetActResult(act=best_candidate, match_kind="partial")


def _find_target_section(
    db: Session, target_act: LegalAct, reference: LegalReference
) -> ActSection | None:
    if reference.target_section_number:
        section = (
            db.query(ActSection)
            .filter(
                ActSection.act_id == target_act.id,
                ActSection.section_number == reference.target_section_number,
            )
            .first()
        )
        if section:
            return section

    target_path = normalize_target_path(reference.target_section_path)
    if not target_path:
        return None

    exact_path = (
        db.query(ActSection)
        .filter(ActSection.act_id == target_act.id, ActSection.section_path == target_path)
        .first()
    )
    if exact_path:
        return exact_path

    schedule = normalize_schedule_reference(target_path)
    if schedule:
        return (
            db.query(ActSection)
            .filter(
                ActSection.act_id == target_act.id,
                ActSection.section_type == SectionType.SCHEDULE,
                or_(
                    ActSection.section_path.ilike(schedule),
                    ActSection.heading.ilike(f"%{schedule}%"),
                    ActSection.text.ilike(f"%{schedule}%"),
                ),
            )
            .first()
        )

    return None


def _mapping_confidence(
    match_kind: str, *, mapped_section: bool, has_structured_target: bool
) -> tuple[float, str]:
    if match_kind == "exact":
        return (0.98 if mapped_section else 0.92, "exact")
    if match_kind == "partial":
        return (0.88 if mapped_section else 0.82, "partial")
    if match_kind == "inferred":
        return (0.78 if mapped_section else 0.68, "inferred")
    return (0.55 if has_structured_target else 0.35, "unresolved")


def _can_use_principal_context(
    reference: LegalReference, context: MappingContext | None
) -> bool:
    if not context or not context.principal_act:
        return False
    if reference.target_act_id or reference.target_act_number or reference.target_act_title_raw:
        return False
    if not (reference.target_section_number or reference.target_section_path):
        return False
    return reference.relationship_type in {
        RelationshipType.AMENDS,
        RelationshipType.REPEALS,
        RelationshipType.INSERTS,
        RelationshipType.SUBSTITUTES,
        RelationshipType.ADDS,
    }


def _is_principal_enactment(value: str | None) -> bool:
    return normalize_act_title(value) == "principal enactment"


def _has_structured_target(reference: LegalReference) -> bool:
    return bool(
        reference.target_act_title_raw
        or reference.target_act_number
        or reference.target_act_year
        or reference.target_section_number
        or reference.target_section_path
    )


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value and value not in seen:
            unique.append(value)
            seen.add(value)
    return unique
